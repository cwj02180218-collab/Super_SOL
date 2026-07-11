from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.measure.shadow import RunFinished, RunPlanned, RunStarted, ShadowWriter
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

_ROW_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def test_shadow_event_keeps_arm_out_of_instruction_payload(tmp_path: Path) -> None:
    # Given a separate shadow stream
    writer = ShadowWriter(tmp_path / "events.jsonl")

    # When an OFF-arm run starts
    writer.append(RunStarted(session_id=SessionId("s1"), arm=HoldoutArm.OFF, model="gpt-5.5"))

    # Then the arm is recorded without any model-visible payload field
    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert '"arm":"off"' in raw
    assert "instructions" not in raw


def test_shadow_schemas_exclude_model_visible_content(tmp_path: Path) -> None:
    # Given every shadow event variant
    writer = ShadowWriter(tmp_path / "events.jsonl")
    events = (
        RunPlanned(
            session_id=SessionId("s1"),
            task_id="task-1",
            arm=HoldoutArm.ON,
            model="gpt-5.6-sol",
            profile=SUPER_SOL_PROFILE.name,
            profile_version=SUPER_SOL_PROFILE.version,
        ),
        RunStarted(session_id=SessionId("s1"), arm=HoldoutArm.ON, model="gpt-5.6-sol"),
        RunFinished(
            session_id=SessionId("s1"),
            arm=HoldoutArm.ON,
            model="gpt-5.6-sol",
            status="abandoned",
            wall_time_seconds=1.25,
            tool_calls=3,
            failed_verifications=1,
            gate_blocks=2,
            input_tokens=100,
            output_tokens=20,
            final_defect_found=None,
            error_type="KeyboardInterrupt",
        ),
    )

    # When all variants are appended
    for event in events:
        writer.append(event)

    # Then no line contains instructions, prompts, packs, or model output
    forbidden = {"instructions", "prompt", "pack_text", "output", "model_output"}
    rows = [
        _ROW_ADAPTER.validate_json(line)
        for line in writer.path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(forbidden.isdisjoint(row) for row in rows)


@pytest.mark.parametrize(
    ("field", "coercive_value"),
    [("wall_time_seconds", "1.25"), ("tool_calls", True), ("input_tokens", "100")],
)
def test_shadow_finished_rejects_coercive_metrics(
    field: str,
    coercive_value: JsonValue,
) -> None:
    # Given an otherwise valid terminal shadow payload with one coercive metric
    payload = RunFinished(
        session_id=SessionId("s1"),
        arm=HoldoutArm.ON,
        model="gpt-5.6-sol",
        status="completed",
        wall_time_seconds=1.25,
        tool_calls=3,
        failed_verifications=0,
        gate_blocks=0,
        input_tokens=100,
        output_tokens=20,
        final_defect_found=None,
        error_type=None,
    ).model_dump()
    payload[field] = coercive_value

    # When the shadow schema parses it
    with pytest.raises(ValidationError):
        _ = RunFinished.model_validate(payload)
