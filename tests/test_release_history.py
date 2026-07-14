"""Historical release claim and evidence contract tests."""

import csv
import hashlib
from pathlib import Path

from tests.package_smoke_support import (
    ANALYSIS_ADAPTER,
    AUDIT_ADAPTER,
    EVIDENCE_MANIFEST_ADAPTER,
)


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
    analysis = ANALYSIS_ADAPTER.validate_json((root / "analysis.json").read_text(encoding="utf-8"))
    audit = AUDIT_ADAPTER.validate_json((root / "audit.json").read_text(encoding="utf-8"))
    manifest = EVIDENCE_MANIFEST_ADAPTER.validate_json(
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
