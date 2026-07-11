from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from fablized_sol.eval.provenance import digest_json


def test_packaged_preregistration_matches_public_contract() -> None:
    public = Path("eval/PREREGISTRATION.md").read_bytes()
    packaged = files("fablized_sol.eval").joinpath("PREREGISTRATION.md").read_bytes()

    assert packaged == public


def test_packaged_dependency_lock_digest_matches_uv_lock() -> None:
    public_digest = sha256(Path("uv.lock").read_bytes()).hexdigest()
    packaged = files("fablized_sol.eval").joinpath("DEPENDENCY_LOCK.sha256").read_text().strip()

    assert packaged == public_digest


def test_canonical_digest_does_not_use_ambiguous_delimiters() -> None:
    left = {"model": "custom:medium", "effort": "low"}
    right = {"model": "custom", "effort": "medium:low"}

    assert digest_json(left) != digest_json(right)
