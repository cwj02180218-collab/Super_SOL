"""Shared typed package-build fixtures for focused smoke modules."""

import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import TypedDict

from pydantic import JsonValue, TypeAdapter


class SdistConfig(TypedDict):
    include: list[str]


class PromotionEvidence(TypedDict):
    gates: dict[str, bool]
    stable_release: bool
    quality_uplift: bool


class AnalysisEvidence(TypedDict):
    protocol: str
    super_sol_promotion: PromotionEvidence


class AttemptCounts(TypedDict):
    attempts: int
    censored: int
    running: int
    valid: int


class AttemptHistory(TypedDict):
    counts: AttemptCounts


class LatticeCounts(TypedDict):
    rows: int


class LatticeAudit(TypedDict):
    counts: LatticeCounts


class AuditEvidence(TypedDict):
    passed: bool
    lattice: LatticeAudit
    attempt_history: AttemptHistory


class EvidenceManifest(TypedDict):
    sha256: dict[str, str]


class TargetsConfig(TypedDict):
    sdist: SdistConfig


class BuildConfig(TypedDict):
    targets: TargetsConfig


class HatchConfig(TypedDict):
    build: BuildConfig


class ToolConfig(TypedDict):
    hatch: HatchConfig


class ProjectConfig(TypedDict):
    tool: ToolConfig


PROJECT_ADAPTER = TypeAdapter[ProjectConfig](ProjectConfig)
JSON_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
STRING_MAP_ADAPTER = TypeAdapter[dict[str, str]](dict[str, str])
ANALYSIS_ADAPTER = TypeAdapter[AnalysisEvidence](AnalysisEvidence)
AUDIT_ADAPTER = TypeAdapter[AuditEvidence](AuditEvidence)
EVIDENCE_MANIFEST_ADAPTER = TypeAdapter[EvidenceManifest](EvidenceManifest)
WHEEL_ASSET_ROOT = "fablized_sol/_release/v0_9"
RELEASE_ASSET_MAP = {
    "plugins/super-sol/.codex-plugin/plugin.json": (
        f"{WHEEL_ASSET_ROOT}/plugin/.codex-plugin/plugin.json"
    ),
    "plugins/super-sol/hooks/__init__.py": f"{WHEEL_ASSET_ROOT}/plugin/hooks/__init__.py",
    "plugins/super-sol/hooks/hooks.json": f"{WHEEL_ASSET_ROOT}/plugin/hooks/hooks.json",
    "plugins/super-sol/hooks/prompt_dispatcher.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/prompt_dispatcher.py"
    ),
    "plugins/super-sol/hooks/super_sol_commands.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_commands.py"
    ),
    "plugins/super-sol/hooks/super_sol_evidence_hook.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_evidence_hook.py"
    ),
    "plugins/super-sol/hooks/super_sol_hook.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_hook.py"
    ),
    "plugins/super-sol/hooks/super_sol_loop_hook.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_loop_hook.py"
    ),
    "plugins/super-sol/hooks/super_sol_loop_policy.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_loop_policy.py"
    ),
    "plugins/super-sol/hooks/super_sol_loop_state.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_loop_state.py"
    ),
    "plugins/super-sol/hooks/super_sol_loop_validation.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_loop_validation.py"
    ),
    "plugins/super-sol/hooks/super_sol_prompt_hook.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_prompt_hook.py"
    ),
    "plugins/super-sol/hooks/super_sol_routes.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_routes.py"
    ),
    "plugins/super-sol/hooks/super_sol_state.py": (
        f"{WHEEL_ASSET_ROOT}/plugin/hooks/super_sol_state.py"
    ),
    "plugins/super-sol/skills/super-sol/SKILL.md": (
        f"{WHEEL_ASSET_ROOT}/plugin/skills/super-sol/SKILL.md"
    ),
    "plugins/super-sol/skills/super-sol/agents/openai.yaml": (
        f"{WHEEL_ASSET_ROOT}/plugin/skills/super-sol/agents/openai.yaml"
    ),
    **{
        f"eval/{name}": f"{WHEEL_ASSET_ROOT}/eval/{name}"
        for name in (
            "v09_loop_audit.py",
            "v09_loop_contract.py",
            "v09_loop_isolation.py",
            "v09_loop_replay.py",
            "v09_loop_runtime.py",
            "v09_loop_seccomp.py",
            "v09_loop_sequences.json",
        )
    },
    "docs/V0.9_PROMOTION_PROTOCOL.md": f"{WHEEL_ASSET_ROOT}/docs/V0.9_PROMOTION_PROTOCOL.md",
    "docs/RELEASE_BRIEF_0.9.0RC1.md": f"{WHEEL_ASSET_ROOT}/docs/RELEASE_BRIEF_0.9.0RC1.md",
    "benchmarks/v0.9-loop-replay/README.md": (
        f"{WHEEL_ASSET_ROOT}/benchmarks/v0.9-loop-replay/README.md"
    ),
    "benchmarks/v0.9-loop-replay/report.json": (
        f"{WHEEL_ASSET_ROOT}/benchmarks/v0.9-loop-replay/report.json"
    ),
}


def nested_object(value: JsonValue, key: str) -> dict[str, JsonValue]:
    assert isinstance(value, dict), key
    return value


def fresh_archives(output_dir: Path) -> tuple[Path, Path]:
    uv = shutil.which("uv")
    assert uv is not None
    completed = subprocess.run(  # noqa: S603
        (uv, "build", "--out-dir", str(output_dir)),
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    sdists = tuple(output_dir.glob("super_sol_harness-0.9.0rc1.tar.gz"))
    wheels = tuple(output_dir.glob("super_sol_harness-0.9.0rc1-py3-none-any.whl"))
    assert len(sdists) == len(wheels) == 1
    return sdists[0], wheels[0]


def archive_members(sdist: Path, wheel: Path) -> tuple[set[str], set[str]]:
    with tarfile.open(sdist) as archive:
        sdist_members = {
            name.split("/", maxsplit=1)[1]
            for member in archive.getmembers()
            if member.isfile() and "/" in (name := member.name)
        }
    with zipfile.ZipFile(wheel) as archive:
        wheel_members = set(archive.namelist())
    return sdist_members, wheel_members


def forbidden_members(members: set[str]) -> set[str]:
    forbidden_parts = {".venv", "plugin-data", "plugin_data", "tests", "chat", "chats"}
    forbidden_names = {".loop-key", "loop.json", "loop.lock", "state.json"}
    return {
        member
        for member in members
        if forbidden_parts.intersection(PurePosixPath(member).parts)
        or PurePosixPath(member).name in forbidden_names
        or "kakao" in member.casefold()
    }
