"""Deterministic prompt classification."""

import re
from typing import Final

from fablized_sol.engine.models import Classification, TaskMode

_CLASSIFICATION_TABLES: Final[tuple[tuple[TaskMode, tuple[re.Pattern[str], ...]], ...]] = (
    (
        TaskMode.DEEP,
        (
            re.compile(
                r"\b(?=.*\b(?:database|db|schema)\b)(?=.*\bmigrat(?:e|ion)\b)",
                re.IGNORECASE,
            ),
            re.compile(r"\b(?:production|prod)\b.*\b(?:deploy|migration)\b", re.IGNORECASE),
            re.compile(r"\b(?:security|architecture|end-to-end|e2e)\b", re.IGNORECASE),
            re.compile(
                r"(?:DB|\ub370\uc774\ud130\ubca0\uc774\uc2a4|\uc2a4\ud0a4\ub9c8).*(?:\ub9c8\uc774\uadf8\ub808\uc774\uc158|\uc774\uad00)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:\ud504\ub85c\ub355\uc158|\uc6b4\uc601).*(?:\ubc30\ud3ec|\ub9c8\uc774\uadf8\ub808\uc774\uc158)"
            ),
            re.compile(r"(?:\ubcf4\uc548|\uc544\ud0a4\ud14d\ucc98|\uc5d4\ub4dc\ud22c\uc5d4\ub4dc)"),
        ),
    ),
    (
        TaskMode.NORMAL,
        (
            re.compile(
                r"\b(?:add|build|change|create|fix|implement|refactor|update|write)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:\uad6c\ud604|\uc218\uc815|\ucd94\uac00|\ubcc0\uacbd|\uc791\uc131|\ub9cc\ub4e4|\ub9ac\ud329\ud130\ub9c1)"
            ),
        ),
    ),
    (
        TaskMode.QUICK,
        (
            re.compile(r"\b(?:explain|summarize|translate|what is|what does)\b", re.IGNORECASE),
            re.compile(
                r"(?:\ubb50\uc57c|\ubb50\uc9c0|\uc124\uba85|\uc694\uc57d|\ubc88\uc5ed|\uc9c8\ubb38)"
            ),
        ),
    ),
)

_RISK_TABLE: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "database",
        re.compile(
            r"\b(?:database|db|migration|schema|sql)\b|(?:DB|\ub370\uc774\ud130\ubca0\uc774\uc2a4|\ub9c8\uc774\uadf8\ub808\uc774\uc158|\uc2a4\ud0a4\ub9c8)",
            re.IGNORECASE,
        ),
    ),
    ("security", re.compile(r"\bsecurity\b|\ubcf4\uc548", re.IGNORECASE)),
    (
        "production",
        re.compile(
            r"\b(?:production|prod)\b|(?:\ud504\ub85c\ub355\uc158|\uc6b4\uc601)",
            re.IGNORECASE,
        ),
    ),
    (
        "destructive",
        re.compile(
            r"\b(?:delete|drop|erase|remove)\b|(?:\uc0ad\uc81c|\ud3d0\uae30)",
            re.IGNORECASE,
        ),
    ),
)


def classify_prompt(prompt: str) -> Classification:
    """Classify a prompt using deterministic ordered signal tables."""
    risk_flags = next(
        ((risk_flag,) for risk_flag, pattern in _RISK_TABLE if pattern.search(prompt)),
        (),
    )
    mode = next(
        (
            candidate
            for candidate, patterns in _CLASSIFICATION_TABLES
            if any(pattern.search(prompt) for pattern in patterns)
        ),
        TaskMode.NORMAL,
    )
    return Classification(mode=mode, risk_flags=risk_flags)
