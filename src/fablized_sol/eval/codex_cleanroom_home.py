"""Symmetric ephemeral Codex homes for clean-room plugin comparisons."""

# The exception messages are the public fail-closed diagnostics for this boundary.
# ruff: noqa: EM101, EM102, TRY003

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, final, override

from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.eval.provenance import digest_json

if TYPE_CHECKING:
    from collections.abc import Mapping

_COMMAND_TIMEOUT_SECONDS: Final = 60
_MAX_CAPTURE_CHARS: Final = 32_768
_MAX_AUTH_BYTES: Final = 1_048_576
_SHA_LENGTH: Final = 40
_IMMUTABLE_REF: Final = re.compile(r"^(?:v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?|[0-9a-f]{40})$")
_PLUGIN_PREFIX: Final = "plugins/cache/super-sol/super-sol/"
_SOURCE_TOKEN: Final = "<PLUGIN_SOURCE>"  # noqa: S105 - digest redaction token, not a secret
_NORMALIZED_TIMESTAMP: Final = "1970-01-01T00:00:00Z"
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


@dataclass(frozen=True, slots=True)
class CleanroomViolation(Exception):  # noqa: N818 - contract term used by public API
    """A home, plugin source, or command violated the clean-room contract."""

    detail: str

    @override
    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class CommandCapture:
    """Bounded output from one local setup command."""

    returncode: int
    stdout: str
    stderr: str


class HomeCommandRunner(Protocol):
    """Process seam used only for Git and stock Codex plugin commands."""

    def run(self, argv: tuple[str, ...], env: Mapping[str, str]) -> CommandCapture:
        """Execute one local command without a shell."""
        ...


@final
class SubprocessHomeCommandRunner:
    """Bounded standard-library implementation of the setup process seam."""

    def run(self, argv: tuple[str, ...], env: Mapping[str, str]) -> CommandCapture:
        """Run one command with an explicit environment and bounded diagnostics."""
        try:
            completed = subprocess.run(  # noqa: S603
                argv,
                check=False,
                capture_output=True,
                env=dict(env),
                text=True,
                timeout=_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return CommandCapture(124, "", "command timed out")
        return CommandCapture(
            completed.returncode,
            completed.stdout[-_MAX_CAPTURE_CHARS:],
            completed.stderr[-_MAX_CAPTURE_CHARS:],
        )


class HomeArm(StrEnum):
    """The two clean-room home variants."""

    RAW = "raw"
    LEAN = "lean"


@dataclass(frozen=True, slots=True)
class HomeTreeEvidence:
    """Secret-free canonical inventory for one home."""

    arm: HomeArm
    tree_digest: str
    files: tuple[str, ...]
    skill_paths: tuple[str, ...]
    plugin_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CleanroomHomes:
    """Owned temporary root and the two validated Codex homes."""

    root: Path
    raw: Path
    lean: Path
    raw_evidence: HomeTreeEvidence
    lean_evidence: HomeTreeEvidence

    @property
    def evidence(self) -> tuple[HomeTreeEvidence, HomeTreeEvidence]:
        """Return both inventories in stable arm order."""
        return (self.raw_evidence, self.lean_evidence)


@dataclass(frozen=True, slots=True)
class _Inventory:
    files: tuple[str, ...]
    directories: tuple[str, ...]
    skill_paths: tuple[str, ...]
    plugin_names: tuple[str, ...]
    tree_digest: str


def _validate_immutable_ref(plugin_ref: str) -> None:
    if _IMMUTABLE_REF.fullmatch(plugin_ref) is None:
        raise CleanroomViolation("plugin ref must be an immutable tag or 40-character commit")


def _parsed_config(path: Path) -> dict[str, JsonValue]:
    try:
        with path.open("rb") as stream:
            parsed: object = tomllib.load(stream)
        return _OBJECT_ADAPTER.validate_python(parsed)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise CleanroomViolation(f"invalid clean-room config: {path}") from error


def _object(value: JsonValue | None, detail: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise CleanroomViolation(detail)
    return value


def _validate_configs(raw_home: Path, lean_home: Path) -> None:
    raw = _parsed_config(raw_home / "config.toml")
    if raw:
        raise CleanroomViolation("raw config must be empty")
    lean = _parsed_config(lean_home / "config.toml")
    if set(lean) != {"marketplaces", "plugins"}:
        raise CleanroomViolation("lean config contains unexpected top-level keys")
    marketplaces = _object(lean.get("marketplaces"), "lean marketplaces must be an object")
    plugins = _object(lean.get("plugins"), "lean plugins must be an object")
    if set(marketplaces) != {"super-sol"}:
        raise CleanroomViolation("lean config must contain exactly one marketplace")
    if set(plugins) != {"super-sol@super-sol"}:
        raise CleanroomViolation("lean config must contain exactly one plugin")
    marketplace = _object(
        marketplaces.get("super-sol"), "Super SOL marketplace config must be an object"
    )
    plugin = _object(
        plugins.get("super-sol@super-sol"), "Super SOL plugin config must be an object"
    )
    if set(marketplace) != {
        "last_updated",
        "source",
        "source_type",
    }:
        raise CleanroomViolation("Super SOL marketplace config is not canonical")
    if marketplace["last_updated"] != _NORMALIZED_TIMESTAMP:
        raise CleanroomViolation("Super SOL marketplace timestamp is not normalized")
    if marketplace["source_type"] != "local":
        raise CleanroomViolation("Super SOL marketplace must be local")
    source = marketplace["source"]
    if not isinstance(source, str) or not source:
        raise CleanroomViolation("Super SOL marketplace source is missing")
    if plugin != {"enabled": True}:
        raise CleanroomViolation("Super SOL plugin config is not canonical")


def _normalized_content(path: Path, relative: str) -> bytes:
    if relative != "config.toml":
        return path.read_bytes()
    parsed = _parsed_config(path)
    marketplaces_value = parsed.get("marketplaces")
    if isinstance(marketplaces_value, dict):
        marketplace_value = marketplaces_value.get("super-sol")
        if isinstance(marketplace_value, dict) and "source" in marketplace_value:
            marketplace = marketplace_value
            marketplace["source"] = _SOURCE_TOKEN
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _inventory(root: Path, arm: HomeArm) -> _Inventory:  # noqa: C901
    if root.is_symlink() or not root.is_dir():
        raise CleanroomViolation(f"{arm} home must be a real directory")
    files: list[str] = []
    directories: list[str] = []
    entries: list[dict[str, object]] = []
    skill_paths: list[str] = []
    plugin_names: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise CleanroomViolation(f"symlink is forbidden in clean-room home: {relative}")
        if relative == "auth.json":
            if not path.is_file():
                raise CleanroomViolation("auth.json must be a regular file")
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        if path.is_dir():
            directories.append(relative)
            entries.append({"kind": "directory", "mode": mode, "path": relative})
            continue
        if not path.is_file():
            raise CleanroomViolation(f"non-regular home entry is forbidden: {relative}")
        files.append(relative)
        content = _normalized_content(path, relative)
        entries.append(
            {
                "content_sha256": sha256(content).hexdigest(),
                "kind": "file",
                "mode": mode,
                "path": relative,
            }
        )
        if relative.endswith("/skills/super-sol/SKILL.md"):
            skill_paths.append(relative)
        if relative.endswith("/.codex-plugin/plugin.json"):
            try:
                manifest = _OBJECT_ADAPTER.validate_json(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, ValidationError) as error:
                raise CleanroomViolation(f"invalid plugin manifest: {relative}") from error
            name = manifest.get("name")
            if not isinstance(name, str):
                raise CleanroomViolation(f"invalid plugin manifest: {relative}")
            plugin_names.append(name)
            version = manifest.get("version")
            if not isinstance(version, str) or path.parent.parent.name != version:
                raise CleanroomViolation("plugin cache version does not match its manifest")
    return _Inventory(
        files=tuple(files),
        directories=tuple(directories),
        skill_paths=tuple(skill_paths),
        plugin_names=tuple(sorted(plugin_names)),
        tree_digest=digest_json({"entries": entries, "schema": "super-sol-codex-home/v1"}),
    )


def validate_home_pair(
    raw_home: Path,
    lean_home: Path,
    plugin_ref: str,
) -> tuple[HomeTreeEvidence, HomeTreeEvidence]:
    """Require a raw home and one-plugin lean home with no other differences."""
    _validate_immutable_ref(plugin_ref)
    _validate_configs(raw_home, lean_home)
    raw = _inventory(raw_home, HomeArm.RAW)
    lean = _inventory(lean_home, HomeArm.LEAN)
    if raw.files != ("config.toml",) or raw.directories:
        raise CleanroomViolation("raw home contains unexpected entries")
    if raw.skill_paths or raw.plugin_names:
        raise CleanroomViolation("raw home contains a plugin")
    if len(lean.skill_paths) != 1:
        raise CleanroomViolation("lean home must contain exactly one Super SOL skill")
    if lean.plugin_names != ("super-sol",):
        raise CleanroomViolation("lean home must contain exactly one Super SOL plugin")
    unexpected_files = tuple(
        path for path in lean.files if path != "config.toml" and not path.startswith(_PLUGIN_PREFIX)
    )
    unexpected_directories = tuple(
        path
        for path in lean.directories
        if not (
            path
            in {
                "plugins",
                "plugins/cache",
                "plugins/cache/super-sol",
                "plugins/cache/super-sol/super-sol",
            }
            or path.startswith(_PLUGIN_PREFIX.rstrip("/"))
        )
    )
    if unexpected_files or unexpected_directories:
        raise CleanroomViolation("lean home contains an unexpected non-plugin difference")
    raw_evidence = HomeTreeEvidence(
        arm=HomeArm.RAW,
        tree_digest=raw.tree_digest,
        files=raw.files,
        skill_paths=raw.skill_paths,
        plugin_names=raw.plugin_names,
    )
    lean_evidence = HomeTreeEvidence(
        arm=HomeArm.LEAN,
        tree_digest=lean.tree_digest,
        files=lean.files,
        skill_paths=lean.skill_paths,
        plugin_names=lean.plugin_names,
    )
    return raw_evidence, lean_evidence


def _checked(
    runner: HomeCommandRunner,
    argv: tuple[str, ...],
    environment: Mapping[str, str],
) -> CommandCapture:
    capture = runner.run(argv, environment)
    if capture.returncode != 0:
        executable = Path(argv[0]).name
        raise CleanroomViolation(f"{executable} clean-room command failed")
    return capture


def _resolved_revision(
    plugin_source: Path,
    plugin_ref: str,
    runner: HomeCommandRunner,
) -> None:
    environment = {"HOME": str(plugin_source.parent), "PATH": os.environ.get("PATH", "")}
    status = _checked(
        runner,
        ("git", "-C", str(plugin_source), "status", "--porcelain"),
        environment,
    )
    if status.stdout.strip():
        raise CleanroomViolation("plugin source must be a clean Git checkout")
    head = _checked(
        runner,
        ("git", "-C", str(plugin_source), "rev-parse", "HEAD"),
        environment,
    ).stdout.strip()
    resolved = _checked(
        runner,
        ("git", "-C", str(plugin_source), "rev-parse", f"{plugin_ref}^{{commit}}"),
        environment,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head) or not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise CleanroomViolation("plugin revision did not resolve to a full commit")
    if head != resolved or (len(plugin_ref) == _SHA_LENGTH and resolved != plugin_ref):
        raise CleanroomViolation("plugin source revision does not match the immutable ref")


def _copy_auth(auth_source: Path | None, homes: tuple[Path, Path]) -> None:
    if auth_source is None:
        return
    if auth_source.is_symlink() or not auth_source.is_file():
        raise CleanroomViolation("auth source must be a regular file")
    if auth_source.stat().st_size > _MAX_AUTH_BYTES:
        raise CleanroomViolation("auth source exceeds the clean-room size limit")
    for home in homes:
        destination = home / "auth.json"
        _ = shutil.copyfile(auth_source, destination)
        destination.chmod(0o600)


def _normalize_lean_config(config: Path, plugin_source: Path) -> None:
    parsed = _parsed_config(config)
    marketplaces = _object(
        parsed.get("marketplaces"), "Codex did not write marketplace configuration"
    )
    marketplace = _object(
        marketplaces.get("super-sol"), "Codex did not write Super SOL marketplace configuration"
    )
    if marketplace.get("source") != str(plugin_source):
        raise CleanroomViolation("Codex marketplace source does not match the plugin checkout")
    normalized = "\n".join(
        (
            "[marketplaces.super-sol]",
            f'last_updated = "{_NORMALIZED_TIMESTAMP}"',
            'source_type = "local"',
            f"source = {json.dumps(str(plugin_source))}",
            "",
            '[plugins."super-sol@super-sol"]',
            "enabled = true",
            "",
        )
    )
    _ = config.write_text(normalized, encoding="utf-8")


def _validate_plugin_listing(capture: CommandCapture) -> None:
    try:
        payload = _OBJECT_ADAPTER.validate_json(capture.stdout)
    except ValidationError as error:
        raise CleanroomViolation("Codex plugin list did not return JSON") from error
    if set(payload) != {"available", "installed"}:
        raise CleanroomViolation("Codex plugin list has an unexpected shape")
    installed = payload.get("installed")
    available = payload.get("available")
    if not isinstance(installed, list) or not isinstance(available, list) or available:
        raise CleanroomViolation("Codex plugin list contains unexpected entries")
    if len(installed) != 1:
        raise CleanroomViolation("Codex must install exactly one plugin")
    plugin = _object(installed[0], "installed plugin entry must be an object")
    if plugin.get("name") != "super-sol" or plugin.get("enabled") is not True:
        raise CleanroomViolation("installed Super SOL plugin is not enabled")


def build_cleanroom_homes(
    codex_binary: Path,
    plugin_source: Path,
    plugin_ref: str,
    auth_source: Path | None,
    runner: HomeCommandRunner,
) -> CleanroomHomes:
    """Build, install, inventory, and return one symmetric temporary home pair."""
    _validate_immutable_ref(plugin_ref)
    if not codex_binary.is_absolute():
        raise CleanroomViolation("Codex binary path must be absolute")
    if plugin_source.is_symlink() or not plugin_source.is_dir():
        raise CleanroomViolation("plugin source must be a real directory")
    source = plugin_source.resolve()
    _resolved_revision(source, plugin_ref, runner)
    root = Path(tempfile.mkdtemp(prefix="super-sol-codex-ab-")).resolve()
    raw = root / "raw"
    lean = root / "lean"
    try:
        raw.mkdir()
        lean.mkdir()
        _ = (raw / "config.toml").write_text("", encoding="utf-8")
        _copy_auth(auth_source, (raw, lean))
        environment = {
            "CODEX_HOME": str(lean),
            "HOME": str(root),
            "PATH": os.environ.get("PATH", ""),
        }
        _ = _checked(
            runner,
            (str(codex_binary), "plugin", "marketplace", "add", str(source), "--json"),
            environment,
        )
        _ = _checked(
            runner,
            (
                str(codex_binary),
                "plugin",
                "add",
                "super-sol",
                "--marketplace",
                "super-sol",
                "--json",
            ),
            environment,
        )
        listing = _checked(
            runner,
            (str(codex_binary), "plugin", "list", "--json"),
            environment,
        )
        _validate_plugin_listing(listing)
        _normalize_lean_config(lean / "config.toml", source)
        for home in (raw, lean):
            for transient in (home / ".tmp", home / "tmp"):
                shutil.rmtree(transient, ignore_errors=True)
        raw_evidence, lean_evidence = validate_home_pair(raw, lean, plugin_ref)
        return CleanroomHomes(root, raw, lean, raw_evidence, lean_evidence)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def remove_cleanroom_homes(homes: CleanroomHomes) -> None:
    """Delete only the owned temporary root represented by validated home paths."""
    root = homes.root.resolve()
    if not root.name.startswith("super-sol-codex-ab-"):
        raise CleanroomViolation("refusing to remove a non-clean-room directory")
    if homes.raw.resolve().parent != root or homes.lean.resolve().parent != root:
        raise CleanroomViolation("clean-room homes are outside their owned root")
    shutil.rmtree(root)
