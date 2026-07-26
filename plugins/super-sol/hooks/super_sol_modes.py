"""Strict operating modes for Super SOL runtime hooks."""

from __future__ import annotations

import os
from enum import Enum

_QUALITY_MODE = "SUPER_SOL_QUALITY_MODE"


class QualityMode(str, Enum):  # noqa: UP042 - plugin runtime supports Python 3.9
    """Whether optional semantic quality guidance may reach the model."""

    SAFETY = "safety"
    SELECTIVE = "selective"


def quality_mode() -> QualityMode:
    """Return selective only for the one exact explicit opt-in value."""
    value = os.environ.get(_QUALITY_MODE, "").strip().casefold()
    return QualityMode.SELECTIVE if value == QualityMode.SELECTIVE else QualityMode.SAFETY
