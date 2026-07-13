"""Installed-package surface smoke tests."""

import csv
import hashlib
from importlib.metadata import distribution, entry_points
from pathlib import Path
from tomllib import load
from typing import TypedDict

from pydantic import TypeAdapter

import fablized_sol


class _SdistConfig(TypedDict):
    include: list[str]


class _PromotionEvidence(TypedDict):
    gates: dict[str, bool]
    stable_release: bool
    quality_uplift: bool


class _AnalysisEvidence(TypedDict):
    protocol: str
    super_sol_promotion: _PromotionEvidence


class _AttemptCounts(TypedDict):
    attempts: int
    censored: int
    running: int
    valid: int


class _AttemptHistory(TypedDict):
    counts: _AttemptCounts


class _LatticeCounts(TypedDict):
    rows: int


class _LatticeAudit(TypedDict):
    counts: _LatticeCounts


class _AuditEvidence(TypedDict):
    passed: bool
    lattice: _LatticeAudit
    attempt_history: _AttemptHistory


class _EvidenceManifest(TypedDict):
    sha256: dict[str, str]


class _TargetsConfig(TypedDict):
    sdist: _SdistConfig


class _BuildConfig(TypedDict):
    targets: _TargetsConfig


class _HatchConfig(TypedDict):
    build: _BuildConfig


class _ToolConfig(TypedDict):
    hatch: _HatchConfig


class _ProjectConfig(TypedDict):
    tool: _ToolConfig


_PROJECT_ADAPTER = TypeAdapter[_ProjectConfig](_ProjectConfig)


def test_console_scripts_are_registered() -> None:
    # Given the project is installed in the uv environment
    expected = {
        "fablized-sol-eval",
        "fablized-sol-report",
        "super-sol-eval",
        "super-sol-report",
        "super-sol-container-audit",
        "super-sol-codex-ab",
        "super-sol-codex-ab-report",
        "super-sol-codex-ab-audit",
    }

    # When its public console-script metadata is selected
    scripts = {script.name for script in entry_points(group="console_scripts")}

    # Then primary and compatibility entry points are registered
    assert expected <= scripts


def test_distribution_uses_super_sol_name() -> None:
    # Given the project is installed in the uv environment
    # When callers inspect its distribution metadata
    name = distribution("super-sol-harness").metadata["Name"]

    # Then the public package uses the Super SOL distribution name
    assert name == "super-sol-harness"


def test_distribution_declares_mit_license() -> None:
    # Given the installed Super SOL distribution
    # When its core metadata is inspected
    license_expression = distribution("super-sol-harness").metadata["License-Expression"]

    # Then downstream users receive a machine-readable MIT license
    assert license_expression == "MIT"


def test_package_exports_version() -> None:
    # Given the project is installed in the uv environment
    # When callers inspect its public package metadata
    version = fablized_sol.__version__

    # Then the package exports the distribution version
    assert version == "0.8.0"


def test_sdist_uses_an_explicit_source_allowlist() -> None:
    # Given the package build configuration
    with Path("pyproject.toml").open("rb") as stream:
        configuration = _PROJECT_ADAPTER.validate_python(load(stream))

    # When the sdist file selection is inspected
    included = set(configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])

    # Then only publishable source and project metadata roots are eligible
    assert included == {
        "/.python-version",
        "/.agents",
        "/AGENTS.md",
        "/CONTRIBUTING.md",
        "/LICENSE",
        "/NOTICE",
        "/README.md",
        "/SECURITY.md",
        "/benchmarks",
        "/docs",
        "/eval",
        "/pyproject.toml",
        "/plugins",
        "/security",
        "/src",
        "/tests",
        "/uv.lock",
    }


def test_readme_exposes_beginner_plugin_and_current_model_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.8.0" in readme
    assert "추가 API 과금 호출 없음" in readme
    assert "gpt-5.6-terra" in readme
    assert "--product-effort" in readme
    assert "--confirm-billable" in readme
    assert "super-sol-container-audit" in readme
    assert "https://openai.com/index/gpt-5-6/" in readme
    assert "GPT-5.6 Sol is a limited preview" not in readme
    assert "v0.8.0 is the stable release" in readme
    assert "super-sol-codex-ab" in readme
    assert "unseen holdout" in readme


def test_readme_exposes_v08_stable_plugin_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    stable_heading = "### 현재 안정판 v0.8.0 설치"

    assert stable_heading in readme
    stable_section = readme.split(stable_heading, maxsplit=1)[1].split(
        "### 새 버전으로 업데이트", maxsplit=1
    )[0]

    assert (
        "codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.8.0" in stable_section
    )
    for hook_event in (
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
    ):
        assert f"`{hook_event}`" in stable_section
    assert "v0.8.0은 현재 안정판입니다." in stable_section


def test_v05_release_candidate_docs_freeze_cells_and_claim_boundary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    postmortem = Path("docs/BENCHMARK_POSTMORTEM_0.4.md").read_text(encoding="utf-8")
    protocol = Path("docs/V0.5_PERFORMANCE_PROTOCOL.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{postmortem}\n{protocol}"

    for expected in (
        "terra-raw",
        "terra-v05",
        "sol-high-raw",
        "sol-max-raw",
        "+5",
        "-2",
        "1.15",
        "0.5.0rc1",
    ):
        assert expected in combined

    assert "v0.3.1" in postmortem

    assert "72 paid slots" in postmortem
    assert "+26.86%" in postmortem
    assert "+30.86%" in postmortem
    assert "-0.50%" in postmortem
    assert "+11.08%" in postmortem
    assert "T109-T116" in protocol
    assert "T117-T124" in protocol
    assert "universal Pro equivalence" in protocol


def test_v05_gate0_brief_stops_before_paid_evidence() -> None:
    brief = Path("docs/RELEASE_BRIEF_0.5.0RC1.md").read_text(encoding="utf-8")

    assert "247 passed" in brief
    assert "90.15%" in brief
    assert "63 passed" in brief
    assert "32 `slot.planned`" in brief
    assert "No v0.5 performance result exists" in brief
    assert "holdout-seal digest: **unavailable" in brief
    assert "SUPER SOL 유료 실행 승인" in brief


def test_v06_diagnostic_docs_freeze_failure_and_four_arm_contract() -> None:
    postmortem = Path("docs/BENCHMARK_POSTMORTEM_0.5.md").read_text(encoding="utf-8")
    protocol = Path("docs/V0.6_DIAGNOSTIC_PROTOCOL.md").read_text(encoding="utf-8")
    combined = f"{postmortem}\n{protocol}"

    for expected in (
        "0.6.0rc1",
        "terra-raw",
        "router-observe",
        "procedure-forced",
        "adaptive-v06",
        "16 paired observations",
        "62.5%",
        "-17.5",
        "T109-T116",
        "64 slots",
        "specialist recall",
        "0.80",
        "0.85",
        "0.90",
    ):
        assert expected in combined

    assert "diagnostic-only" in protocol
    assert "no performance promotion" in protocol


def test_v06_gate0_brief_makes_no_performance_claim() -> None:
    brief = Path("docs/RELEASE_BRIEF_0.6.0RC1.md").read_text(encoding="utf-8")

    assert "255 passed" in brief
    assert "45 passed" in brief
    assert "90.15%" in brief
    assert "no known vulnerabilities found" in brief
    assert "No v0.6 model slot was executed" in brief
    assert "sealed T125-T132 holdout" in brief


def test_v07_candidate_docs_freeze_evidence_bounded_claim() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    postmortem = Path("docs/BENCHMARK_POSTMORTEM_0.6.md").read_text(encoding="utf-8")
    protocol = Path("docs/V0.7_PROMOTION_PROTOCOL.md").read_text(encoding="utf-8")
    brief = Path("docs/RELEASE_BRIEF_0.7.0RC1.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{postmortem}\n{protocol}\n{brief}"

    for expected in (
        "0.7.0rc1",
        "raw-first",
        "one model-visible injection",
        "T117-T124",
        "64 valid slots",
        "token ratio <= 1.05",
        "wall-time ratio <= 1.10",
        "not a performance-uplift claim",
        "Terra -0.71",
        "Sol +2.53",
    ):
        assert expected in combined


def test_v08_release_budget_spec_freezes_latency_and_profile_privacy_gates() -> None:
    plan = Path("docs/superpowers/plans/2026-07-13-super-sol-v0.8-masterpiece.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(plan.split())

    for expected in (
        "300 real prompt-hook invocations",
        "150 empty Python processes",
        "Assert absolute p95 below 100 ms and incremental p95 below 70 ms",
        "Sol, Terra, Luna, missing-model, and malformed-model",
        "every file is at most 4096 bytes",
    ):
        assert expected in normalized


def test_v08_candidate_docs_freeze_sol_only_evidence_boundary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    product = Path("docs/SUPER_SOL.md").read_text(encoding="utf-8")
    protocol = Path("docs/V0.8_PROMOTION_PROTOCOL.md").read_text(encoding="utf-8")
    brief = Path("docs/RELEASE_BRIEF_0.8.0RC1.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{product}\n{protocol}\n{brief}"

    for expected in (
        "0.8.0rc1",
        "0.8.0-rc1",
        "gpt-5.6-sol",
        "180 Unicode code points",
        "observation-only",
        "additional API call",
        "96/96 valid slots",
        "Sol/high validation is pending",
        "uplift was not proven",
    ):
        assert expected in combined

    assert "raises underlying model intelligence" in combined
    assert "performance amplifier" not in brief


def test_v08_stable_release_records_confirmatory_evidence_without_uplift_claim() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    brief = Path("docs/RELEASE_BRIEF_0.8.0.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{brief}"

    for expected in (
        "0.8.0",
        "96/96 valid slots",
        "mean paired score delta: 0.00",
        "95% clustered bootstrap CI: [0.00, 0.00]",
        "paired token ratio: 0.9767",
        "paired wall-time ratio: 1.0791",
        "noninferior quality with bounded overhead",
        "quality uplift was not proven",
    ):
        assert expected in combined


def test_v08_public_evidence_implements_the_frozen_promotion_contract() -> None:
    root = Path("benchmarks/v0.8-confirmatory")
    analysis = TypeAdapter(_AnalysisEvidence).validate_json(
        (root / "analysis.json").read_text(encoding="utf-8")
    )
    audit = TypeAdapter(_AuditEvidence).validate_json(
        (root / "audit.json").read_text(encoding="utf-8")
    )
    manifest = TypeAdapter(_EvidenceManifest).validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    gates = analysis["super_sol_promotion"]["gates"]

    assert analysis["protocol"] == "v08-four-arm-analysis-v2"
    assert set(gates) == {
        "mean_score_noninferior",
        "score_ci_lower_at_least_minus_2",
        "full_pass_rate_not_lower",
        "token_ratio_at_most_1_03",
        "time_ratio_at_most_1_10",
        "no_repeated_10_point_regression",
        "verifier_observation_rate_not_lower",
        "exact_96_valid_slots_after_linked_retries",
        "hidden_test_leak_zero",
        "artifact_omission_zero",
        "contamination_zero",
        "provenance_mismatch_zero",
        "secret_count_zero",
    }
    assert all(gates.values())
    assert analysis["super_sol_promotion"]["stable_release"] is True
    assert analysis["super_sol_promotion"]["quality_uplift"] is False
    assert audit["passed"] is True
    assert audit["lattice"]["counts"]["rows"] == 96
    assert audit["attempt_history"]["counts"] == {
        "attempts": 103,
        "censored": 7,
        "running": 0,
        "valid": 96,
    }

    with (root / "slots.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 96
    with (root / "attempts.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 103

    for name, expected in manifest["sha256"].items():
        path = root / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    published = "\n".join(
        path.read_text(encoding="utf-8") for path in root.iterdir() if path.is_file()
    )
    assert "/Users/" not in published
    assert "/private/var/" not in published
