"""Shared fixtures for hook latency gate tests."""

import json
from pathlib import Path

from pydantic import JsonValue

EXACT_COMMAND = '/usr/bin/python3 -S "$PLUGIN_ROOT/hooks/prompt_dispatcher.py"'


def plugin_root(
    tmp_path: Path,
    command: str = EXACT_COMMAND,
    timeout: JsonValue = 5,
) -> Path:
    """Create a minimal plugin tree with one configured prompt hook."""
    root = tmp_path / "plugin"
    hooks = root / "hooks"
    hooks.mkdir(parents=True)
    _ = (hooks / "prompt_dispatcher.py").write_text("", encoding="utf-8")
    _ = (hooks / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": command,
                                    "timeout": timeout,
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return root
