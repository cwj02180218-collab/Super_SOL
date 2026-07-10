"""Deterministic routing for holdout-isolated procedure packs."""

import re
from dataclasses import dataclass
from enum import StrEnum, unique
from importlib.resources import files
from pathlib import Path
from typing import Final, assert_never

from fablized_sol.engine.classify_task import classify_prompt
from fablized_sol.engine.models import Classification, HoldoutArm


@unique
class PackName(StrEnum):
    """Experimental instruction pack identifier."""

    INVESTIGATION = "investigation"
    GROUNDING = "grounding"
    MULTI_STORY = "multi_story"


@dataclass(frozen=True, slots=True)
class InstructionRequest:
    """Inputs required to build model-visible instructions."""

    prompt: str
    base: str
    arm: HoldoutArm
    pack_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class InstructionBundle:
    """Model instructions and out-of-band routing metadata."""

    instructions: str
    classification: Classification
    pack_names: tuple[PackName, ...]


_PACK_SIGNALS: Final[tuple[tuple[PackName, re.Pattern[str]], ...]] = (
    (
        PackName.INVESTIGATION,
        re.compile(
            r"""
            \b(?:bug|debug(?:ger|ging)?|failure|race[ ]condition|regression|reproduce)\b
            |(?:\ub514\ubc84\uadf8|\ubc84\uadf8|\uc624\ub958|\uc2e4\ud328|\uc7ac\ud604)
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    (
        PackName.GROUNDING,
        re.compile(
            r"""
            \b(?:artifact|audio|image|pdf|render|screenshot|video)\b
            |(?:\uc0b0\ucd9c\ubb3c|\ub80c\ub354|PDF|\uc774\ubbf8\uc9c0|\uc2a4\ud06c\ub9b0\uc0f7|\uc601\uc0c1)
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    (
        PackName.MULTI_STORY,
        re.compile(
            r"""
            \b(?:(?:multiple|several|two|three|\d+)\s+(?:independent\s+)?
            |independent\s+|separate\s+)(?:deliverables?|outcomes?|stories?|tasks?)\b
            |(?:\uc5ec\ub7ec|\ub3c5\ub9bd\uc801\uc778|\uac01\uac01\uc758)\s*(?:\uacb0\uacfc|\uc0b0\ucd9c\ubb3c|\uc791\uc5c5)
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
)


def _matched_packs(prompt: str) -> tuple[PackName, ...]:
    return tuple(pack_name for pack_name, pattern in _PACK_SIGNALS if pattern.search(prompt))


def _read_pack(pack_name: PackName, pack_dir: Path | None) -> str:
    filename = f"{pack_name.value}.txt"
    if pack_dir is not None:
        return (pack_dir / filename).read_text(encoding="utf-8").strip()
    return files("fablized_sol.packs").joinpath(filename).read_text(encoding="utf-8").strip()


def build_instructions(request: InstructionRequest) -> InstructionBundle:
    """Build arm-isolated instructions and retain routing metadata out of band."""
    classification = classify_prompt(request.prompt)
    match request.arm:
        case HoldoutArm.OFF:
            return InstructionBundle(
                instructions=request.base,
                classification=classification,
                pack_names=(),
            )
        case HoldoutArm.ON:
            pack_names = _matched_packs(request.prompt)
        case _:
            assert_never(request.arm)

    risks = ", ".join(classification.risk_flags) or "none"
    context = f"[Task context]\nMode: {classification.mode.value}\nRisk: {risks}"
    pack_sections = tuple(
        f"[Pack: {pack_name.value}]\n{_read_pack(pack_name, request.pack_dir)}"
        for pack_name in pack_names
    )
    return InstructionBundle(
        instructions="\n\n".join((request.base, context, *pack_sections)),
        classification=classification,
        pack_names=pack_names,
    )
