from collections.abc import Mapping
from typing import TypedDict

import pytest

from fablized_sol.eval.codex_cleanroom import CodexArm
from fablized_sol.measure.codex_ab import (
    CodexABReportError,
    build_candidate_report,
    finalize_promotion,
)
from fablized_sol.measure.codex_ab_models import CodexABAudit, CodexABSample


class _SampleKwargs(TypedDict, total=False):
    score_deltas: Mapping[str, float]
    lean_full_pass: bool
    lean_tokens: int
    lean_time: float


def samples(
    *,
    score_deltas: Mapping[str, float] | None = None,
    lean_full_pass: bool = True,
    lean_tokens: int = 1020,
    lean_time: float = 10.5,
) -> tuple[CodexABSample, ...]:
    deltas = score_deltas or {"t1": 1.0, "t2": 1.0}
    result: list[CodexABSample] = []
    for task_id in ("t1", "t2"):
        for repetition in (1, 2):
            common: dict[str, object] = {
                "task_id": task_id,
                "repetition": repetition,
                "run_digest": "a" * 64,
                "task_digest": ("b" if task_id == "t1" else "c") * 64,
                "codex_binary_digest": "d" * 64,
                "plugin_ref": "e" * 40,
                "raw_home_digest": "f" * 64,
                "lean_home_digest": "0" * 64,
            }
            result.append(
                CodexABSample.model_validate(
                    common
                    | {
                        "arm": CodexArm.RAW,
                        "score": 90.0,
                        "full_pass": True,
                        "total_tokens": 1000,
                        "wall_time_seconds": 10.0,
                    }
                )
            )
            result.append(
                CodexABSample.model_validate(
                    common
                    | {
                        "arm": CodexArm.LEAN,
                        "score": 90.0 + deltas[task_id],
                        "full_pass": lean_full_pass,
                        "total_tokens": lean_tokens,
                        "wall_time_seconds": lean_time,
                    }
                )
            )
    return tuple(result)


def test_every_preregistered_gate_must_pass() -> None:
    candidate = build_candidate_report(samples(), seed=20260711)
    decision = finalize_promotion(
        candidate,
        CodexABAudit(artifact_omissions=0, leakage_findings=0, aggregate_reproduced=True),
    )

    assert decision.promote is True
    assert {gate.name for gate in decision.gates if not gate.passed} == set()
    assert len(decision.gates) == 9


@pytest.mark.parametrize(
    ("sample_kwargs", "artifact_omissions", "leakage_findings", "failed_gate"),
    [
        ({"score_deltas": {"t1": -1.0, "t2": -1.0}}, 0, 0, "mean_score_uplift"),
        ({"score_deltas": {"t1": -5.0, "t2": 5.0}}, 0, 0, "bootstrap_lower_bound"),
        ({"lean_full_pass": False}, 0, 0, "full_pass_rate"),
        ({"lean_tokens": 1060}, 0, 0, "token_budget"),
        ({"lean_time": 11.1}, 0, 0, "wall_time_budget"),
        (
            {"score_deltas": {"t1": -10.0, "t2": 10.0}},
            0,
            0,
            "repeated_task_regression",
        ),
        ({}, 1, 0, "artifact_completeness"),
        ({}, 0, 1, "hidden_test_leakage"),
    ],
)
def test_one_failed_gate_blocks_promotion(
    sample_kwargs: _SampleKwargs,
    artifact_omissions: int,
    leakage_findings: int,
    failed_gate: str,
) -> None:
    candidate = build_candidate_report(samples(**sample_kwargs), seed=20260711)
    decision = finalize_promotion(
        candidate,
        CodexABAudit(
            artifact_omissions=artifact_omissions,
            leakage_findings=leakage_findings,
            aggregate_reproduced=True,
        ),
    )

    assert decision.promote is False
    assert next(gate for gate in decision.gates if gate.name == failed_gate).passed is False


def test_missing_or_duplicate_cell_rejects_report() -> None:
    with pytest.raises(CodexABReportError, match="complete lattice"):
        _ = build_candidate_report(samples()[:-1], seed=20260711)

    with pytest.raises(CodexABReportError, match="complete lattice"):
        _ = build_candidate_report((*samples(), samples()[0]), seed=20260711)


def test_failed_independent_reproduction_blocks_promotion() -> None:
    candidate = build_candidate_report(samples(), seed=20260711)
    decision = finalize_promotion(
        candidate,
        CodexABAudit(artifact_omissions=0, leakage_findings=0, aggregate_reproduced=False),
    )

    assert decision.promote is False
    audit_gate = next(gate for gate in decision.gates if gate.name == "independent_audit")
    assert audit_gate.passed is False
