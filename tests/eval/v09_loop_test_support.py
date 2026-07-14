from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable


class IsolationHandle(Protocol):
    preexec_fn: Callable[[], None] | None

    def close(self) -> None: ...


class IsolationModule(Protocol):
    NETWORK_SYSCALLS: tuple[str, ...]
    SANDBOX: Path
    kernel_platform: Callable[[], str]
    kernel_machine: Callable[[], str]
    kernel_library_finder: Callable[[str], str | None]

    def linux_isolation(self, library: object | None = None) -> IsolationHandle: ...

    def network_probe_sources(self) -> tuple[str, str]: ...

    def probe_launcher_environment(self) -> dict[str, str]: ...

    def require_kernel_network_deny(self) -> dict[str, object]: ...


class ReplayModule(Protocol):
    def audit_network_capabilities(self, plugin_root: Path) -> dict[str, object]: ...

    def build_report(
        self, manifest: Path | dict[str, object], plugin_root: Path
    ) -> dict[str, object]: ...


ROOT = Path(__file__).parents[2]
_ = sys.path.insert(0, str(ROOT / "eval"))


def isolation_module() -> IsolationModule:
    module = importlib.import_module("v09_loop_isolation")
    return cast("IsolationModule", cast("object", module))


def replay_module() -> ReplayModule:
    module = importlib.import_module("v09_loop_replay")
    return cast("ReplayModule", cast("object", module))
