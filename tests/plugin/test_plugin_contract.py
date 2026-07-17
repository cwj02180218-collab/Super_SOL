import ast
import json
import re
import tomllib
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
    assert manifest["version"] == "0.9.1-rc1"
    assert manifest["repository"] == "https://github.com/cwj02180218-collab/Super_SOL"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    interface = manifest["interface"]
    assert isinstance(interface, dict)
    long_description = interface["longDescription"]
    assert isinstance(long_description, str)
    for expected in (
        "`gpt-5.6-sol`과 `gpt-5.6-terra`에서 선택적 의미 개입",
        "그 외 모델은 observation-only",
        "루프 퓨즈는 `gpt-5.6-sol` 전용",
        "추가 model/API call, 모델 전환, 자동 재시도는 없습니다.",
    ):
        assert expected in long_description
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
    assert set(hooks) == {
        "PostCompact",
        "PostToolUse",
        "PreCompact",
        "PreToolUse",
        "SubagentStart",
        "SubagentStop",
        "UserPromptSubmit",
    }
    for event, groups in hooks.items():
        assert isinstance(groups, list)
        group = groups[0]
        assert isinstance(group, dict)
        handlers = group["hooks"]
        assert isinstance(handlers, list)
        handler = handlers[0]
        assert isinstance(handler, dict)
        assert handler["timeout"] == 5
        assert isinstance(handler["statusMessage"], str)
        if event != "UserPromptSubmit":
            assert (
                handler["command"] == '/usr/bin/python3 -S "$PLUGIN_ROOT/hooks/super_sol_hook.py"'
            )
    for event in ("PreToolUse", "PostToolUse"):
        configured = hooks[event]
        assert isinstance(configured, list)
        group = configured[0]
        assert isinstance(group, dict)
        assert group["matcher"] == ".*"
    encoded = json.dumps(hooks)
    assert "prompt_dispatcher.py" in encoded
    assert "$PLUGIN_ROOT/hooks/super_sol_hook.py" in encoded
    assert "commandWindows" in encoded
    assert "command_windows" not in encoded
    assert "http://" not in encoded
    assert "https://" not in encoded
    assert (PLUGIN_ROOT / "hooks" / "prompt_dispatcher.py").is_file()


def test_v091_rc_versions_and_release_contract_are_consistent() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = _json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    brief_path = REPO_ROOT / "docs" / "RELEASE_BRIEF_0.9.1RC1.md"
    protocol_path = REPO_ROOT / "docs" / "V0.9.1_PROMOTION_PROTOCOL.md"

    assert project["project"]["version"] == "0.9.1rc1"
    assert manifest["version"] == "0.9.1-rc1"
    assert brief_path.is_file()
    assert protocol_path.is_file()
    brief = brief_path.read_text(encoding="utf-8")
    protocol = protocol_path.read_text(encoding="utf-8")
    normalized_protocol = " ".join(protocol.split())

    for document in (readme, brief):
        normalized = " ".join(document.casefold().split())
        for expected in (
            "v0.9.1-rc1",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "selective semantic intervention",
            "two successful distinct edits",
            "one prompt context",
            "one evidence context",
            "no model calls",
            "no retries",
            "quality uplift has not been established",
            "240 valid slots have not run",
        ):
            assert expected in normalized

    for expected in (
        "Gate 0",
        "Gate 1",
        "30 new tasks",
        "240 valid slots",
        "Sol/high",
        "Terra/xhigh",
        "fresh homes",
        "fresh worktrees",
        "mean paired score delta at least 0",
        "task-clustered 95% CI lower bound at least -2",
        "token ratio at most 1.03",
        "wall-time ratio at most 1.05",
        "zero contamination",
        "quality uplift requires",
        "separate explicit billable approval",
    ):
        assert expected in normalized_protocol

    for document in (readme, brief):
        assert "fablized_sol/_release/v0_9_1/" in document


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
    assert not re.search(r"(?im)^\s*(?:\d+\.\s+|-\s+)(?:retry|continue)\b", skill)


def test_loop_fuse_manifest_has_no_stop_hook() -> None:
    hooks = _json(PLUGIN_ROOT / "hooks" / "hooks.json")["hooks"]

    assert isinstance(hooks, dict)
    assert "Stop" not in hooks


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
