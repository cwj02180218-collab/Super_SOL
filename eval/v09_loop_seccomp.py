from __future__ import annotations

import ctypes
import errno
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable

KERNEL_ERROR = "kernel_isolation"
SECCOMP_ALLOW = 0x7FFF0000
SECCOMP_ERRNO = 0x00050000 | errno.EPERM
LINUX_ARCHITECTURES = frozenset({"aarch64", "arm64", "amd64", "x86_64"})
NETWORK_SYSCALLS = (
    "socket",
    "socketpair",
    "bind",
    "connect",
    "listen",
    "accept",
    "accept4",
    "getsockname",
    "getpeername",
    "sendto",
    "sendmsg",
    "sendmmsg",
    "recvfrom",
    "recvmsg",
    "recvmmsg",
    "shutdown",
    "setsockopt",
    "getsockopt",
    "io_uring_setup",
    "io_uring_enter",
    "io_uring_register",
    "bpf",
    "pidfd_getfd",
)


class CFunction(Protocol):
    argtypes: list[object]
    restype: object

    def __call__(self, *args: object) -> object: ...


class SeccompLibrary(Protocol):
    seccomp_init: CFunction
    seccomp_load: CFunction
    seccomp_release: CFunction
    seccomp_rule_add: CFunction
    seccomp_syscall_resolve_name: CFunction


def _configure(library: SeccompLibrary) -> None:
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int


def _load_library(name: str) -> SeccompLibrary:
    try:
        library = cast("SeccompLibrary", cast("object", ctypes.CDLL(name, use_errno=True)))
    except OSError as error:
        raise ValueError(KERNEL_ERROR) from error
    return library


def _add_rules(library: SeccompLibrary, context: int) -> bool:
    for syscall in NETWORK_SYSCALLS:
        number = cast("int", library.seccomp_syscall_resolve_name(syscall.encode()))
        if number < 0:
            return False
        result = cast("int", library.seccomp_rule_add(context, SECCOMP_ERRNO, number, 0))
        if result != 0:
            return False
    return True


def seccomp_callbacks(
    machine: str,
    library_finder: Callable[[str], str | None],
    provided_library: object | None = None,
) -> tuple[Callable[[], None], Callable[[], None]]:
    if machine.lower() not in LINUX_ARCHITECTURES:
        raise ValueError(KERNEL_ERROR)
    library_name = library_finder("seccomp") if provided_library is None else None
    if provided_library is None and library_name is None:
        raise ValueError(KERNEL_ERROR)
    library = (
        _load_library(cast("str", library_name))
        if provided_library is None
        else cast("SeccompLibrary", provided_library)
    )
    try:
        _configure(library)
    except AttributeError as error:
        raise ValueError(KERNEL_ERROR) from error
    context = cast("int | None", library.seccomp_init(SECCOMP_ALLOW))
    if context is None:
        raise ValueError(KERNEL_ERROR)

    def release() -> None:
        _ = library.seccomp_release(context)

    try:
        rules_added = _add_rules(library, context)
    except (ctypes.ArgumentError, OSError) as error:
        release()
        raise ValueError(KERNEL_ERROR) from error
    if not rules_added:
        release()
        raise ValueError(KERNEL_ERROR)

    def load() -> None:
        result = cast("int", library.seccomp_load(context))
        if result != 0:
            raise OSError(errno.EPERM, KERNEL_ERROR)

    return load, release
