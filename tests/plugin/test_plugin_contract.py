import ast
import json
from pathlib import Path

from .conftest import HOOK_SCRIPT, PLUGIN_ROOT, REPO_ROOT


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_plugin_manifest_and_marketplace_are_release_ready() -> None:
    manifest = _json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    marketplace = _json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")

    assert manifest["name"] == "super-sol"
    assert manifest["version"] == "0.3.0"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    entries = marketplace["plugins"]
    assert isinstance(entries, list)
    assert entries[0]["source"]["path"] == "./plugins/super-sol"


def test_hook_config_registers_only_local_python_commands() -> None:
    hooks = _json(PLUGIN_ROOT / "hooks" / "hooks.json")["hooks"]
    assert isinstance(hooks, dict)
    assert set(hooks) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    encoded = json.dumps(hooks)
    assert "$PLUGIN_ROOT/hooks/super_sol_hook.py" in encoded
    assert "http://" not in encoded
    assert "https://" not in encoded


def test_skill_is_concise_implicit_and_stock_codex_only() -> None:
    skill = (PLUGIN_ROOT / "skills" / "super-sol" / "SKILL.md").read_text(encoding="utf-8")
    metadata = (PLUGIN_ROOT / "skills" / "super-sol" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )

    assert "[TODO:" not in skill
    assert len(skill.splitlines()) < 120
    assert "allow_implicit_invocation: true" in metadata
    lowered = skill.lower()
    assert "lazycodex" not in lowered
    assert "omo" not in lowered


def test_hook_runtime_has_no_network_process_or_openai_imports() -> None:
    tree = ast.parse(HOOK_SCRIPT.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imports.isdisjoint({"openai", "requests", "httpx", "urllib", "subprocess"})
    source = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in source
