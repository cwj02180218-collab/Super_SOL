"""Validate the Claude Code plugin package that ships with this repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(relative: str) -> dict[str, object]:
    raw = cast("object", json.loads((REPO_ROOT / relative).read_text(encoding="utf-8")))
    return _as_dict(raw)


def _as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast("list[object]", value)


def _as_str(value: object) -> str:
    assert isinstance(value, str)
    return value


def test_plugin_manifest_is_valid() -> None:
    manifest = _load(".claude-plugin/plugin.json")
    assert manifest["name"] == "super-sol"
    assert _as_str(manifest["version"])
    skills = _as_list(manifest["skills"])
    assert skills
    for skill in skills:
        skill_path = _as_str(skill)
        assert (REPO_ROOT / skill_path / "SKILL.md").is_file()


def test_marketplace_manifest_is_valid() -> None:
    marketplace = _load(".claude-plugin/marketplace.json")
    assert marketplace["name"] == "super-sol"
    plugins = _as_list(marketplace["plugins"])
    assert len(plugins) == 1
    entry = _as_dict(plugins[0])
    assert entry["name"] == "super-sol"
    assert entry["source"] == "./"


def test_plugin_versions_match_package() -> None:
    manifest = _load(".claude-plugin/plugin.json")
    marketplace = _load(".claude-plugin/marketplace.json")
    metadata = _as_dict(marketplace["metadata"])
    assert metadata["version"] == manifest["version"]


def test_command_files_reference_existing_scripts() -> None:
    commands = sorted((REPO_ROOT / "commands").glob("*.md"))
    assert {path.name for path in commands} >= {"setup.md", "eval.md", "report.md"}
    for path in commands:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{path.name} is missing frontmatter"
        assert "description:" in text.splitlines()[1]
    assert (REPO_ROOT / "scripts/setup.sh").is_file()


def test_setup_script_is_offline_and_fail_closed() -> None:
    script = (REPO_ROOT / "scripts/setup.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    assert "--dry-run" in script
    assert "OPENAI_API_KEY" not in script
