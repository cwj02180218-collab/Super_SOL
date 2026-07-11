import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fablized_sol.eval.manifest import EvalOptions, ManifestParseError, TaskManifest


def _write_manifest(
    tmp_path: Path,
    *,
    fixture: str = "fixture",
    task_id: str = "python-logic",
    verify_argv: str | list[str] | None = None,
) -> Path:
    fixture_path = tmp_path / fixture
    fixture_path.mkdir(exist_ok=True)
    path = tmp_path / "tasks.json"
    payload = {
        "tasks": [
            {
                "id": task_id,
                "prompt": "Diagnose and fix the failing test.",
                "fixture": fixture,
                "verify_argv": verify_argv or ["uv", "run", "pytest", "-q"],
            }
        ]
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_manifest_rejects_shell_string_for_verification(tmp_path: Path) -> None:
    # Given a manifest whose verification command is an unparsed shell string
    path = _write_manifest(tmp_path, verify_argv="pytest -q")

    # When the trust boundary parses the manifest
    with pytest.raises(ManifestParseError):
        _ = TaskManifest.load(path)


def test_manifest_resolves_fixture_relative_to_manifest(tmp_path: Path) -> None:
    # Given a relative fixture path in a manifest
    path = _write_manifest(tmp_path)

    # When the manifest is loaded independently of the caller's working directory
    manifest = TaskManifest.load(path)

    # Then the fixture becomes the manifest-relative absolute directory
    assert manifest.tasks[0].fixture == (tmp_path / "fixture").resolve()


def test_manifest_rejects_duplicate_task_ids(tmp_path: Path) -> None:
    # Given two otherwise valid tasks with the same identifier
    path = _write_manifest(tmp_path)
    task = {
        "id": "python-logic",
        "prompt": "Diagnose and fix the failing test.",
        "fixture": "fixture",
        "verify_argv": ["uv", "run", "pytest", "-q"],
    }
    _ = path.write_text(json.dumps({"tasks": [task, task]}), encoding="utf-8")

    # When the manifest is loaded
    with pytest.raises(ManifestParseError, match="duplicate task id"):
        _ = TaskManifest.load(path)


def test_manifest_rejects_fixture_file(tmp_path: Path) -> None:
    # Given a manifest whose fixture exists but is not a directory
    fixture = tmp_path / "fixture-file"
    _ = fixture.write_text("not a directory", encoding="utf-8")
    path = _write_manifest(tmp_path, fixture="valid-fixture")
    payload = {
        "tasks": [
            {
                "id": "python-logic",
                "prompt": "Diagnose and fix the failing test.",
                "fixture": fixture.name,
                "verify_argv": ["uv", "run", "pytest", "-q"],
            }
        ]
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")

    # When the manifest is loaded
    with pytest.raises(ManifestParseError, match="fixture directory"):
        _ = TaskManifest.load(path)


def test_manifest_rejects_symlink_inside_fixture(tmp_path: Path) -> None:
    # Given a fixture that contains a symlink to an external file
    path = _write_manifest(tmp_path)
    outside = tmp_path / "outside.py"
    _ = outside.write_text("secret", encoding="utf-8")
    (tmp_path / "fixture" / "linked.py").symlink_to(outside)

    # When the manifest crosses the trust boundary, then copying is refused
    with pytest.raises(ManifestParseError, match="symlink"):
        _ = TaskManifest.load(path)


def test_manifest_wraps_invalid_json_with_path(tmp_path: Path) -> None:
    # Given malformed JSON at the manifest boundary
    path = tmp_path / "tasks.json"
    _ = path.write_text("{", encoding="utf-8")

    # When the loader parses it
    with pytest.raises(ManifestParseError, match=str(path)):
        _ = TaskManifest.load(path)


def test_eval_options_reject_identical_comparison_models(tmp_path: Path) -> None:
    # Given both comparison roles name the same model
    # When evaluation options cross the typed boundary
    with pytest.raises(ValidationError, match="comparison models must be distinct"):
        _ = EvalOptions(
            tasks=tmp_path / "tasks.json",
            output_dir=tmp_path / "out",
            run_id="duplicate-models",
            models=("gpt-5.5", "gpt-5.5"),
            max_gate_retries=2,
            dry_run=True,
            verification_image=None,
        )


def test_live_eval_options_require_digest_pinned_verification_image(tmp_path: Path) -> None:
    # Given live evaluation options without a verification container image
    # When options cross the trust boundary, then validation fails closed
    with pytest.raises(ValidationError, match="verification image"):
        _ = EvalOptions(
            tasks=tmp_path / "tasks.json",
            output_dir=tmp_path / "out",
            run_id="live",
            models=("gpt-5.6-sol", "gpt-5.5"),
            max_gate_retries=2,
            dry_run=False,
            verification_image=None,
        )


def test_eval_options_reject_mutable_verification_image_tag(tmp_path: Path) -> None:
    # Given a mutable image tag
    # When options cross the trust boundary, then only a digest is accepted
    with pytest.raises(ValidationError, match="sha256"):
        _ = EvalOptions(
            tasks=tmp_path / "tasks.json",
            output_dir=tmp_path / "out",
            run_id="live",
            models=("gpt-5.6-sol", "gpt-5.5"),
            max_gate_retries=2,
            dry_run=False,
            verification_image="python:3.12",
        )
