"""Expected behavior for the intentionally defective arithmetic fixture."""

from calc import add


def test_add_returns_sum() -> None:
    """Addition should return the mathematical sum."""
    expected = 5
    assert add(2, 3) == expected  # noqa: S101
