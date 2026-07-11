import json
from pathlib import Path

from fablized_sol.measure.codex_ab import build_candidate_report
from fablized_sol.measure.codex_ab_audit import audit_codex_ab
from fablized_sol.measure.codex_ab_models import CodexABAudit

from .test_codex_ab import samples


def test_auditor_reproduces_aggregates_and_detects_hidden_material(tmp_path: Path) -> None:
    artifacts = tmp_path / "public"
    artifacts.mkdir()
    events = artifacts / "events.jsonl"
    _ = events.write_text(
        "\n".join(
            json.dumps({"type": "slot.completed"} | sample.model_dump(mode="json"))
            for sample in samples()
        )
        + "\n",
        encoding="utf-8",
    )
    _ = (artifacts / "run.json").write_text(
        '{"schema":"super-sol-codex-ab/v1"}\n', encoding="utf-8"
    )
    candidate = artifacts / "candidate.json"
    _ = candidate.write_text(
        build_candidate_report(samples(), seed=20260711).model_dump_json(), encoding="utf-8"
    )

    clean = audit_codex_ab(events, candidate, artifacts)

    assert clean == CodexABAudit(
        artifact_omissions=0,
        leakage_findings=0,
        aggregate_reproduced=True,
    )

    hidden = artifacts / "hidden-tests.py"
    _ = hidden.write_text("def test_private_contract(): assert True\n", encoding="utf-8")

    leaked = audit_codex_ab(events, candidate, artifacts)

    assert leaked.leakage_findings == 1


def test_auditor_detects_candidate_aggregate_tampering(tmp_path: Path) -> None:
    artifacts = tmp_path / "public"
    artifacts.mkdir()
    events = artifacts / "events.jsonl"
    _ = events.write_text(
        "\n".join(
            json.dumps({"type": "slot.completed"} | sample.model_dump(mode="json"))
            for sample in samples()
        )
        + "\n",
        encoding="utf-8",
    )
    _ = (artifacts / "run.json").write_text("{}\n", encoding="utf-8")
    candidate_path = artifacts / "candidate.json"
    candidate = build_candidate_report(samples(), seed=20260711)
    tampered = candidate.model_copy(update={"mean_score_delta": 99.0})
    _ = candidate_path.write_text(tampered.model_dump_json(), encoding="utf-8")

    audit = audit_codex_ab(events, candidate_path, artifacts)

    assert audit.aggregate_reproduced is False
