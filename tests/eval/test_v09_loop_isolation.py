from __future__ import annotations

import ctypes
import shutil
import socket
import threading
from typing import TYPE_CHECKING, Never, cast

import pytest

from .v09_loop_test_support import ROOT, isolation_module, replay_module

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MANIFEST = ROOT / "eval" / "v09_loop_sequences.json"
PLUGIN = ROOT / "plugins" / "super-sol"


class _FakeFunction:
    _implementation: Callable[..., object]

    def __init__(self, implementation: Callable[..., object]) -> None:
        self.argtypes: list[object] = []
        self.restype: object = None
        self.calls: list[tuple[object, ...]] = []
        self._implementation = implementation

    def __call__(self, *args: object) -> object:
        self.calls.append(args)
        return self._implementation(*args)


class _FakeSeccomp:
    seccomp_init: _FakeFunction
    seccomp_load: _FakeFunction
    seccomp_release: _FakeFunction
    seccomp_rule_add: _FakeFunction
    seccomp_syscall_resolve_name: _FakeFunction

    def __init__(self, *, rule_result: int = 0, rule_error: Exception | None = None) -> None:
        def context(_action: object) -> int:
            return 17

        def success(*_args: object) -> int:
            return 0

        def resolve(_name: object) -> int:
            return 101

        def add_rule(*_args: object) -> int:
            if rule_error is not None:
                raise rule_error
            return rule_result

        self.seccomp_init = _FakeFunction(context)
        self.seccomp_load = _FakeFunction(success)
        self.seccomp_release = _FakeFunction(success)
        self.seccomp_rule_add = _FakeFunction(add_rule)
        self.seccomp_syscall_resolve_name = _FakeFunction(resolve)


def test_linux_seccomp_abi_rules_load_and_single_release() -> None:
    module = isolation_module()
    library = _FakeSeccomp()

    handle = module.linux_isolation(library)

    assert library.seccomp_init.argtypes == [ctypes.c_uint32]
    assert library.seccomp_init.restype is ctypes.c_void_p
    assert library.seccomp_rule_add.argtypes == [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    assert len(library.seccomp_rule_add.calls) == len(module.NETWORK_SYSCALLS)
    assert handle.preexec_fn is not None
    handle.preexec_fn()
    assert library.seccomp_load.calls == [(17,)]
    handle.close()
    handle.close()
    assert library.seccomp_release.calls == [(17,)]


def test_linux_seccomp_rule_failure_releases_context() -> None:
    module = isolation_module()
    library = _FakeSeccomp(rule_result=-1)

    with pytest.raises(ValueError, match="kernel_isolation"):
        _ = module.linux_isolation(library)

    assert library.seccomp_release.calls == [(17,)]


def test_linux_seccomp_rule_exception_releases_context() -> None:
    module = isolation_module()
    library = _FakeSeccomp(rule_error=ctypes.ArgumentError("fixture-rule"))

    with pytest.raises(ValueError, match="kernel_isolation"):
        _ = module.linux_isolation(library)

    assert library.seccomp_release.calls == [(17,)]


def test_socket_creation_permission_error_passes_both_network_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_socket(*_args: object, **_kwargs: object) -> Never:
        raise PermissionError

    monkeypatch.setattr(socket, "socket", deny_socket)
    probes = isolation_module().network_probe_sources()

    assert len(probes) == 2
    for probe in probes:
        with pytest.raises(SystemExit) as raised:
            exec(probe, {})  # noqa: S102 - executes shipped self-test source only.
        assert raised.value.code == 0


def test_hostile_parent_credentials_are_absent_from_actual_hook_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = {
        "OPENAI_API_KEY": "fixture-openai-secret-91c5",
        "CODEX_API_KEY": "fixture-codex-secret-a873",
        "SUPER_SOL_FORCED_ROUTE": "fixture-route-secret-3d62",
        "AWS_ACCESS_KEY_ID": "fixture-aws-access-120b",
        "AWS_SECRET_ACCESS_KEY": "fixture-aws-secret-55f0",
        "AWS_SESSION_TOKEN": "fixture-aws-session-802e",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)

    observed = isolation_module().probe_launcher_environment()

    assert {"PATH", "PLUGIN_DATA", "PLUGIN_ROOT", "PYTHONUTF8"} <= set(observed)
    assert set(hostile).isdisjoint(observed)
    assert all(secret not in value for secret in hostile.values() for value in observed.values())


def test_unsupported_platform_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = isolation_module()
    monkeypatch.setattr(module, "kernel_platform", lambda: "fixture-os")

    with pytest.raises(ValueError, match="kernel_isolation"):
        _ = module.require_kernel_network_deny()


def test_linux_without_libseccomp_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = isolation_module()

    def missing_library(_name: str) -> None:
        return None

    monkeypatch.setattr(module, "kernel_platform", lambda: "Linux")
    monkeypatch.setattr(module, "kernel_machine", lambda: "x86_64")
    monkeypatch.setattr(module, "kernel_library_finder", missing_library)

    with pytest.raises(ValueError, match="kernel_isolation"):
        _ = module.require_kernel_network_deny()


def test_kernel_network_deny_self_test_is_enforced() -> None:
    evidence = isolation_module().require_kernel_network_deny()
    assert evidence == {
        "required": True,
        "enforced": True,
        "benign_child": "passed",
        "connect": "denied",
        "bind": "denied",
    }


def test_missing_sandbox_dynamic_socket_probe_fails_without_server_hit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.05)
    port = cast("tuple[str, int]", listener.getsockname())[1]
    hits: list[int] = []
    stopped = threading.Event()

    def accept_connections() -> None:
        while not stopped.is_set():
            try:
                connection = cast("tuple[socket.socket, object]", listener.accept())[0]
            except TimeoutError:
                continue
            except OSError:
                return
            hits.append(1)
            connection.close()

    worker = threading.Thread(target=accept_connections)
    worker.start()
    plugin = tmp_path / "plugin"
    _ = shutil.copytree(PLUGIN, plugin)
    hook = plugin / "hooks" / "super_sol_hook.py"
    source = hook.read_text(encoding="utf-8")
    probe = (
        "\nimport builtins\n"
        "try:\n"
        "    fixture_socket = builtins.__import__('socket').create_connection(\n"
        f"        ('127.0.0.1', {port})\n"
        "    )\n"
        "    fixture_socket.close()\n"
        "except OSError:\n"
        "    pass\n"
    )
    source = source.replace(
        "from __future__ import annotations\n", "from __future__ import annotations\n" + probe
    )
    _ = hook.write_text(source, encoding="utf-8")
    monkeypatch.setattr(isolation_module(), "SANDBOX", tmp_path / "missing-sandbox")
    failure: ValueError | None = None
    try:
        _ = replay_module().build_report(MANIFEST, plugin)
    except ValueError as error:
        failure = error
    finally:
        stopped.set()
        listener.close()
        worker.join(timeout=1)

    assert failure is not None
    assert str(failure) == "kernel_isolation"
    assert hits == []
