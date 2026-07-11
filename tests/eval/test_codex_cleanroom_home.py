import json
from collections.abc import Mapping
from pathlib import Path
from typing import final

import pytest

from fablized_sol.eval.codex_cleanroom_home import (
    CleanroomViolation,
    CommandCapture,
    HomeArm,
    build_cleanroom_homes,
    remove_cleanroom_homes,
    validate_home_pair,
)

_REVISION = "a" * 40
_PLUGIN_CONFIG = """[marketplaces.super-sol]
last_updated = "1970-01-01T00:00:00Z"
source_type = "local"
source = "<PLUGIN_SOURCE>"

[plugins."super-sol@super-sol"]
enabled = true
"""


def _write_valid_pair(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw"
    lean = tmp_path / "lean"
    raw.mkdir()
    lean.mkdir()
    _ = (raw / "config.toml").write_text("", encoding="utf-8")
    _ = (lean / "config.toml").write_text(_PLUGIN_CONFIG, encoding="utf-8")
    plugin = lean / "plugins" / "cache" / "super-sol" / "super-sol" / "0.4.0-rc1"
    (plugin / "skills" / "super-sol").mkdir(parents=True)
    _ = (plugin / "skills" / "super-sol" / "SKILL.md").write_text(
        "---\nname: super-sol\n---\n", encoding="utf-8"
    )
    (plugin / ".codex-plugin").mkdir()
    _ = (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "super-sol", "version": "0.4.0-rc1"}), encoding="utf-8"
    )
    return raw, lean


def test_home_pair_allows_only_one_pinned_super_sol_plugin(tmp_path: Path) -> None:
    raw, lean = _write_valid_pair(tmp_path)

    raw_evidence, lean_evidence = validate_home_pair(raw, lean, _REVISION)

    assert raw_evidence.arm is HomeArm.RAW
    assert lean_evidence.arm is HomeArm.LEAN
    assert raw_evidence.skill_paths == ()
    assert len(lean_evidence.skill_paths) == 1
    assert raw_evidence.plugin_names == ()
    assert lean_evidence.plugin_names == ("super-sol",)
    assert raw_evidence.tree_digest != lean_evidence.tree_digest


@pytest.mark.parametrize("extra", ["another-plugin", "second-super-sol-skill", "raw-file"])
def test_home_pair_rejects_every_unexpected_difference(tmp_path: Path, extra: str) -> None:
    raw, lean = _write_valid_pair(tmp_path)
    if extra == "another-plugin":
        path = lean / "plugins" / "cache" / "other" / "plugin.json"
        path.parent.mkdir(parents=True)
        _ = path.write_text('{"name":"other","version":"1.0.0"}', encoding="utf-8")
    elif extra == "second-super-sol-skill":
        path = lean / "duplicate" / "skills" / "super-sol" / "SKILL.md"
        path.parent.mkdir(parents=True)
        _ = path.write_text("---\nname: super-sol\n---\n", encoding="utf-8")
    else:
        _ = (raw / "unexpected.toml").write_text("enabled = true\n", encoding="utf-8")

    with pytest.raises(CleanroomViolation):
        _ = validate_home_pair(raw, lean, _REVISION)


@pytest.mark.parametrize("plugin_ref", ["main", "latest", "HEAD", "refs/heads/release"])
def test_mutable_plugin_ref_is_rejected(tmp_path: Path, plugin_ref: str) -> None:
    raw, lean = _write_valid_pair(tmp_path)

    with pytest.raises(CleanroomViolation, match="immutable"):
        _ = validate_home_pair(raw, lean, plugin_ref)


def test_symlink_in_home_is_rejected(tmp_path: Path) -> None:
    raw, lean = _write_valid_pair(tmp_path)
    target = lean / "outside.txt"
    _ = target.write_text("outside\n", encoding="utf-8")
    (lean / "plugins" / "linked.txt").symlink_to(target)

    with pytest.raises(CleanroomViolation, match="symlink"):
        _ = validate_home_pair(raw, lean, _REVISION)


@final
class _FakeHomeRunner:
    plugin_source: Path
    revision: str
    calls: list[tuple[tuple[str, ...], dict[str, str]]]

    def __init__(self, plugin_source: Path, revision: str) -> None:
        self.plugin_source = plugin_source
        self.revision = revision
        self.calls = []

    def run(self, argv: tuple[str, ...], env: Mapping[str, str]) -> CommandCapture:
        environment = dict(env)
        self.calls.append((argv, environment))
        if argv[:3] == ("git", "-C", str(self.plugin_source)):
            if argv[3:] == ("status", "--porcelain"):
                return CommandCapture(0, "", "")
            return CommandCapture(0, f"{self.revision}\n", "")
        home = Path(environment["CODEX_HOME"])
        if argv[1:4] == ("plugin", "marketplace", "add"):
            config = "\n".join(
                (
                    "[marketplaces.super-sol]",
                    'last_updated = "2026-07-11T00:00:00Z"',
                    'source_type = "local"',
                    f'source = "{self.plugin_source}"',
                    "",
                )
            )
            _ = (home / "config.toml").write_text(config, encoding="utf-8")
            return CommandCapture(0, '{"marketplaceName":"super-sol"}', "")
        if argv[1:3] == ("plugin", "add"):
            with (home / "config.toml").open("a", encoding="utf-8") as stream:
                _ = stream.write('\n[plugins."super-sol@super-sol"]\nenabled = true\n')
            plugin = home / "plugins" / "cache" / "super-sol" / "super-sol" / "0.4.0-rc1"
            (plugin / "skills" / "super-sol").mkdir(parents=True)
            _ = (plugin / "skills" / "super-sol" / "SKILL.md").write_text(
                "name: super-sol\n", encoding="utf-8"
            )
            (plugin / ".codex-plugin").mkdir()
            _ = (plugin / ".codex-plugin" / "plugin.json").write_text(
                '{"name":"super-sol","version":"0.4.0-rc1"}', encoding="utf-8"
            )
            return CommandCapture(0, '{"pluginId":"super-sol@super-sol"}', "")
        listing = {
            "installed": [
                {
                    "pluginId": "super-sol@super-sol",
                    "name": "super-sol",
                    "enabled": True,
                    "version": "0.4.0-rc1",
                }
            ],
            "available": [],
        }
        return CommandCapture(0, json.dumps(listing), "")


def test_build_homes_keeps_auth_out_of_evidence_and_cleans_up(tmp_path: Path) -> None:
    plugin_source = tmp_path / "source"
    plugin_source.mkdir()
    auth = tmp_path / "auth.json"
    _ = auth.write_text('{"tokens":{"access_token":"secret-value"}}', encoding="utf-8")
    runner = _FakeHomeRunner(plugin_source, _REVISION)

    homes = build_cleanroom_homes(
        codex_binary=Path("/opt/codex"),
        plugin_source=plugin_source,
        plugin_ref=_REVISION,
        auth_source=auth,
        runner=runner,
    )

    assert "secret-value" not in repr(homes)
    assert (homes.raw / "auth.json").stat().st_mode & 0o777 == 0o600
    assert (homes.lean / "auth.json").stat().st_mode & 0o777 == 0o600
    assert "auth.json" not in homes.raw_evidence.files
    assert "auth.json" not in homes.lean_evidence.files
    assert all("secret-value" not in capture for call in runner.calls for capture in call[0])
    remove_cleanroom_homes(homes)
    assert not homes.root.exists()


def test_build_homes_rejects_dirty_or_wrong_revision_and_cleans_up(tmp_path: Path) -> None:
    plugin_source = tmp_path / "source"
    plugin_source.mkdir()
    runner = _FakeHomeRunner(plugin_source, "b" * 40)

    with pytest.raises(CleanroomViolation, match="revision"):
        _ = build_cleanroom_homes(
            codex_binary=Path("/opt/codex"),
            plugin_source=plugin_source,
            plugin_ref=_REVISION,
            auth_source=None,
            runner=runner,
        )
