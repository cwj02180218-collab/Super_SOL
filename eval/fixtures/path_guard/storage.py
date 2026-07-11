from pathlib import Path


class PathTraversalError(Exception):
    pass


def resolve_under(root: Path, user_path: str) -> Path:
    return (root / user_path).resolve()
