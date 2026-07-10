from pathlib import Path

import pytest

from fablized_sol.engine.models import HoldoutArm, TaskMode
from fablized_sol.harness.router import (
    InstructionRequest,
    PackName,
    build_instructions,
)


@pytest.fixture
def pack_dir(tmp_path: Path) -> Path:
    investigation = (
        "Reproduce the observed failure first. Isolate one falsifiable hypothesis, test it, "
        "then make the smallest change and rerun the narrow verification."
    )
    grounding = (
        "Inspect the actual artifact before judging it. Render, execute, or parse it with an "
        "appropriate tool and base conclusions on that observed result."
    )
    multi_story = (
        "Split independent outcomes into explicit stories. Close each story only with concrete "
        "evidence, and reserve the final story for end-to-end verification."
    )
    _ = (tmp_path / "investigation.txt").write_text(investigation, encoding="utf-8")
    _ = (tmp_path / "grounding.txt").write_text(grounding, encoding="utf-8")
    _ = (tmp_path / "multi_story.txt").write_text(multi_story, encoding="utf-8")
    return tmp_path


def test_debug_prompt_routes_only_investigation_pack(pack_dir: Path) -> None:
    # Given an ON-arm debugging request
    request = InstructionRequest(
        prompt="재현되지 않는 race condition을 디버그해줘",
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then only the investigation procedure is model-visible
    assert bundle.pack_names == (PackName.INVESTIGATION,)
    assert "reproduce" in bundle.instructions.lower()
    assert "render" not in bundle.instructions.lower()
    assert "split independent outcomes" not in bundle.instructions.lower()


def test_artifact_render_prompt_routes_only_grounding_pack(pack_dir: Path) -> None:
    # Given an ON-arm request to inspect a rendered artifact
    request = InstructionRequest(
        prompt="Render the PDF artifact and inspect the result",
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then only grounding guidance is appended
    assert bundle.pack_names == (PackName.GROUNDING,)
    assert "actual artifact" in bundle.instructions.lower()
    assert "reproduce" not in bundle.instructions.lower()
    assert "split independent outcomes" not in bundle.instructions.lower()


def test_explicit_multi_outcome_prompt_routes_only_multi_story_pack(pack_dir: Path) -> None:
    # Given an ON-arm request with explicit independent outcomes
    request = InstructionRequest(
        prompt="Implement three independent outcomes as separate deliverables",
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then only multi-story guidance is appended
    assert bundle.pack_names == (PackName.MULTI_STORY,)
    assert "explicit stories" in bundle.instructions.lower()
    assert "reproduce" not in bundle.instructions.lower()
    assert "actual artifact" not in bundle.instructions.lower()


def test_combined_signals_route_each_matching_pack_once(pack_dir: Path) -> None:
    # Given a prompt matching every experimental procedure
    request = InstructionRequest(
        prompt=(
            "Debug the PDF render failure and deliver two independent outcomes as separate tasks"
        ),
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then all and only matched packs are routed in stable order
    assert bundle.pack_names == (
        PackName.INVESTIGATION,
        PackName.GROUNDING,
        PackName.MULTI_STORY,
    )
    assert bundle.instructions.lower().count("reproduce") == 1
    assert bundle.instructions.lower().count("actual artifact") == 1
    assert bundle.instructions.lower().count("explicit stories") == 1


def test_holdout_receives_base_byte_for_byte_without_experimental_labels(
    pack_dir: Path,
) -> None:
    # Given a risky prompt in the OFF arm and whitespace-sensitive base text
    base = "  BASE\r\nwith trailing whitespace  \n"
    request = InstructionRequest(
        prompt="Debug this production database migration failure",
        base=base,
        arm=HoldoutArm.OFF,
        pack_dir=pack_dir / "missing",
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then the model receives only the byte-for-byte base instruction
    assert bundle.instructions == base
    assert bundle.pack_names == ()
    assert all(
        label not in bundle.instructions.lower()
        for label in ("mode", "risk", "arm", "pack", "holdout")
    )


def test_on_arm_appends_classification_without_arm_label(pack_dir: Path) -> None:
    # Given a classified ON-arm request without a pack signal
    request = InstructionRequest(
        prompt="Migrate the database schema",
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then mode and risk are visible without leaking experiment assignment
    assert bundle.classification.mode is TaskMode.DEEP
    assert bundle.classification.risk_flags == ("database",)
    assert bundle.pack_names == ()
    assert "Mode: deep" in bundle.instructions
    assert "Risk: database" in bundle.instructions
    assert "arm" not in bundle.instructions.lower()
    assert "holdout" not in bundle.instructions.lower()


def test_default_package_resources_supply_matched_pack() -> None:
    # Given an ON-arm request using installed package resources
    request = InstructionRequest(
        prompt="Render this image artifact before judging it",
        base="BASE",
        arm=HoldoutArm.ON,
    )

    # When instructions are built
    bundle = build_instructions(request)

    # Then the packaged grounding text is available
    assert bundle.pack_names == (PackName.GROUNDING,)
    assert "Render, execute, or parse" in bundle.instructions
