"""Stable experiment holdout assignment."""

from hashlib import sha256

from fablized_sol.engine.models import HoldoutArm, SessionId


def assign_arm(session_id: SessionId) -> HoldoutArm:
    """Assign a session to the deterministic 20 percent holdout arm."""
    value = int.from_bytes(sha256(session_id.encode()).digest()[:8], byteorder="big", signed=False)
    return HoldoutArm.OFF if value % 5 == 0 else HoldoutArm.ON
