from pathlib import Path

import pytest
from storage import PathTraversalError, resolve_under


def test_parent_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        _ = resolve_under(tmp_path / "root", "../outside.txt")
