import ast
import json
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from .conftest import PLUGIN_ROOT, REPO_ROOT

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def _json(path: Path) -> dict[str, JsonValue]:
    return _OBJECT_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def test_plugin_manifest_and_marketplace_are_release_ready() -> None:
    manifest = _json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    marketplace = _json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")

    assert manifest["name"] == "super-sol"
    assert manifest["version"] == "0.4.0-rc1"
    assert manifest["repository"] == "https://github.com/cwj02180218-collab/Super_SOL"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    entries = marketplace["plugins"]
    assert isinstance(entries, list)
    entry = entries[0]
    assert isinstance(entry, dict)
    source = entry["source"]
    assert isinstance(source, dict)
    assert source["path"] == "./plugins/super-sol"


def test_hook_config_registers_only_local_python_commands() -> None:
    hooks = _json(PLUGIN_ROOT / "hooks" / "hooks.json")["hooks"]
    assert isinstance(hooks, dict)
    assert set(hooks) == {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    encoded = json.dumps(hooks)
    assert "$PLUGIN_ROOT/hooks/super_sol_hook.py" in encoded
    assert "commandWindows" in encoded
    assert "command_windows" not in encoded
    assert "http://" not in encoded
    assert "https://" not in encoded


def test_skill_is_concise_explicit_and_stock_codex_only() -> None:
    skill = (PLUGIN_ROOT / "skills" / "super-sol" / "SKILL.md").read_text(encoding="utf-8")
    metadata = (PLUGIN_ROOT / "skills" / "super-sol" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )

    assert "[TODO:" not in skill
    assert len(skill.splitlines()) < 120
    assert "allow_implicit_invocation: false" in metadata
    lowered = skill.lower()
    assert "lazycodex" not in lowered
    assert "omo" not in lowered


def test_hook_runtime_has_no_network_process_or_openai_imports() -> None:
    sources = tuple((PLUGIN_ROOT / "hooks").glob("*.py"))
    imports = {
        alias.name.split(".", maxsplit=1)[0]
        for source in sources
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".", maxsplit=1)[0]
        for source in sources
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imports.isdisjoint({"openai", "requests", "httpx", "urllib", "subprocess"})
    assert all("OPENAI_API_KEY" not in source.read_text(encoding="utf-8") for source in sources)
