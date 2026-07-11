from pathlib import Path

from support import call_subject


def test_absolute_path_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    response = call_subject(
        {
            "kind": "function",
            "module": "storage",
            "name": "resolve_under",
            "args": [str(root), str(tmp_path / "outside.txt")],
            "path_args": [0],
        }
    )
    assert response == {"ok": False, "error": "PathTraversalError"}


def test_sibling_prefix_is_not_treated_as_descendant(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    response = call_subject(
        {
            "kind": "function",
            "module": "storage",
            "name": "resolve_under",
            "args": [str(root), "../data-copy/file.txt"],
            "path_args": [0],
        }
    )
    assert response == {"ok": False, "error": "PathTraversalError"}


def test_normal_child_resolves_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    response = call_subject(
        {
            "kind": "function",
            "module": "storage",
            "name": "resolve_under",
            "args": [str(root), "nested/file.txt"],
            "path_args": [0],
        }
    )
    assert response == {"ok": True, "result": str(root / "nested/file.txt")}
