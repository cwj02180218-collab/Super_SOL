from __future__ import annotations

import ctypes.util
import json
import os
import platform
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from v09_loop_seccomp import (  # pyright: ignore[reportImplicitRelativeImport]
    KERNEL_ERROR,
    NETWORK_SYSCALLS,
    seccomp_callbacks,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

SANDBOX = Path("/usr/bin/sandbox-exec")
SANDBOX_PROFILE = "(version 1) (deny network*) (allow default)"
LAUNCHER_ENV_KEYS = ("PATH", "PLUGIN_DATA", "PLUGIN_ROOT", "PYTHONUTF8")
CREDENTIAL_FIXTURES = {
    "OPENAI_API_KEY": "fixture-openai-secret-91c5",
    "CODEX_API_KEY": "fixture-codex-secret-a873",
    "SUPER_SOL_FORCED_ROUTE": "fixture-route-secret-3d62",
    "AWS_ACCESS_KEY_ID": "fixture-aws-access-120b",
    "AWS_SECRET_ACCESS_KEY": "fixture-aws-secret-55f0",
    "AWS_SESSION_TOKEN": "fixture-aws-session-802e",
}
CREDENTIAL_KEYS = tuple(sorted(CREDENTIAL_FIXTURES))
__all__ = ["NETWORK_SYSCALLS"]
CONNECT_PROBE = """
import socket

try:
    sock = socket.socket()
    sock.connect(("127.0.0.1", 9))
except PermissionError:
    raise SystemExit(0)
except OSError:
    raise SystemExit(2)
raise SystemExit(3)
"""
BIND_PROBE = """
import socket

try:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
except PermissionError:
    raise SystemExit(0)
except OSError:
    raise SystemExit(2)
raise SystemExit(3)
"""
ENVIRONMENT_PROBE = """
import json
import os

print(json.dumps(dict(os.environ), sort_keys=True))
"""

kernel_platform: Callable[[], str] = platform.system
kernel_machine: Callable[[], str] = platform.machine
kernel_library_finder: Callable[[str], str | None] = ctypes.util.find_library


@dataclass
class KernelIsolation:
    command_prefix: tuple[str, ...] = ()
    preexec_fn: Callable[[], None] | None = None
    release_fn: Callable[[], None] | None = None
    _closed: bool = field(default=False, init=False)

    def wrap(self, command: tuple[str, ...]) -> tuple[str, ...]:
        return (*self.command_prefix, *command)

    def close(self) -> None:
        if self.release_fn is not None and not self._closed:
            self.release_fn()
        self._closed = True


def linux_isolation(library: object | None = None) -> KernelIsolation:
    load, release = seccomp_callbacks(kernel_machine(), kernel_library_finder, library)
    return KernelIsolation(preexec_fn=load, release_fn=release)


def _macos_isolation() -> KernelIsolation:
    if not SANDBOX.is_file() or not os.access(SANDBOX, os.X_OK):
        raise ValueError(KERNEL_ERROR)
    return KernelIsolation(command_prefix=(str(SANDBOX), "-p", SANDBOX_PROFILE))


def isolated_run(
    isolation: KernelIsolation,
    command: tuple[str, ...],
    *,
    env: dict[str, str],
    input_text: str | None = None,
    timeout: int = 5,
) -> subprocess.CompletedProcess[str]:
    wrapped = isolation.wrap(command)
    if isolation.preexec_fn is None:
        return subprocess.run(  # noqa: S603
            wrapped,
            capture_output=True,
            check=False,
            env=env,
            input=input_text,
            text=True,
            timeout=timeout,
        )
    return subprocess.run(  # noqa: S603
        wrapped,
        capture_output=True,
        check=False,
        env=env,
        input=input_text,
        preexec_fn=isolation.preexec_fn,
        text=True,
        timeout=timeout,
    )


def network_probe_sources() -> tuple[str, str]:
    return CONNECT_PROBE, BIND_PROBE


def _self_test(isolation: KernelIsolation) -> bool:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONUTF8": "1"}
    scripts = ("raise SystemExit(0)", *network_probe_sources())
    try:
        completed = [
            isolated_run(isolation, (sys.executable, "-I", "-c", script), env=env)
            for script in scripts
        ]
    except (OSError, subprocess.SubprocessError):
        return False
    return all(result.returncode == 0 for result in completed)


def kernel_evidence() -> dict[str, object]:
    return {
        "required": True,
        "enforced": True,
        "benign_child": "passed",
        "connect": "denied",
        "bind": "denied",
    }


def kernel_isolation() -> KernelIsolation:
    system = kernel_platform()
    if system == "Darwin":
        isolation = _macos_isolation()
    elif system == "Linux":
        isolation = linux_isolation()
    else:
        raise ValueError(KERNEL_ERROR)
    if not _self_test(isolation):
        isolation.close()
        raise ValueError(KERNEL_ERROR)
    return isolation


def require_kernel_network_deny() -> dict[str, object]:
    isolation = kernel_isolation()
    isolation.close()
    return kernel_evidence()


def launcher_environment(
    plugin_root: Path,
    plugin_data: Path,
    parent: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if parent is None else parent
    return {
        "PLUGIN_ROOT": str(plugin_root),
        "PLUGIN_DATA": str(plugin_data),
        "PATH": source.get("PATH", ""),
        "PYTHONUTF8": "1",
    }


def observe_launcher_environment(
    isolation: KernelIsolation, parent: Mapping[str, str]
) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="super-sol-env-probe-") as directory:
        root = Path(directory)
        hook = root / "environment_hook.py"
        _ = hook.write_text(ENVIRONMENT_PROBE, encoding="utf-8")
        command = f"/usr/bin/python3 -S {shlex.quote(str(hook))}"
        completed = isolated_run(
            isolation,
            ("/bin/sh", "-c", command),
            env=launcher_environment(root, root / "data", parent),
        )
    if completed.returncode != 0:
        raise ValueError(KERNEL_ERROR)
    observed = _string_mapping(cast("object", json.loads(completed.stdout)))
    if observed is None:
        raise ValueError(KERNEL_ERROR)
    return observed


def _string_mapping(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    mapping = cast("dict[object, object]", value)
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in mapping.items()):
        return None
    return {cast("str", key): cast("str", item) for key, item in mapping.items()}


def probe_launcher_environment() -> dict[str, str]:
    isolation = kernel_isolation()
    try:
        return observe_launcher_environment(isolation, os.environ)
    finally:
        isolation.close()


def environment_evidence(isolation: KernelIsolation) -> dict[str, object]:
    hostile_parent = {**os.environ, **CREDENTIAL_FIXTURES}
    observed = observe_launcher_environment(isolation, hostile_parent)
    if not set(CREDENTIAL_KEYS).isdisjoint(observed):
        raise ValueError(KERNEL_ERROR)
    if any(
        secret in value for secret in CREDENTIAL_FIXTURES.values() for value in observed.values()
    ):
        raise ValueError(KERNEL_ERROR)
    return {
        "launcher_env_keys": list(LAUNCHER_ENV_KEYS),
        "credential_keys_absent": list(CREDENTIAL_KEYS),
    }
