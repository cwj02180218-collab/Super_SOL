from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, cast

import pytest

from .v09_loop_test_support import ROOT, replay_module

if TYPE_CHECKING:
    from pathlib import Path

PLUGIN = ROOT / "plugins" / "super-sol"


@pytest.mark.parametrize(
    "fixture",
    [
        "import socket\n",
        "import http.client\n",
        "import urllib.request\n",
        "import requests\n",
        "import subprocess\n",
        "import importlib\n",
        "__import__('fixture-module')\n",
        "import builtins\nbuiltins.__import__('socket')\n",
        "from builtins import __import__ as imp\nimp('socket')\n",
        "import os\nos.system('curl fixture-target')\n",
        "import os\nos.execvp('fixture-program', ['fixture-program'])\n",
        "from os import execvp as run\nrun('fixture-program', ['fixture-program'])\n",
        "import os\nos.posix_spawn('fixture-program', ['fixture-program'], {})\n",
    ],
)
def test_network_capability_audit_fails_closed(tmp_path: Path, fixture: str) -> None:
    plugin = tmp_path / "plugin"
    _ = shutil.copytree(PLUGIN, plugin)
    nested = plugin / "hooks" / "fixture-nested"
    nested.mkdir()
    _ = (nested / "fixture_escape.py").write_text(fixture, encoding="utf-8")

    with pytest.raises(ValueError, match="network_capability"):
        _ = replay_module().audit_network_capabilities(plugin)


def test_network_capability_audit_rejects_symlinked_hook_code(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    _ = shutil.copytree(PLUGIN, plugin)
    outside = tmp_path / "fixture-outside.py"
    _ = outside.write_text("fixture_value = 1\n", encoding="utf-8")
    (plugin / "hooks" / "fixture-link.py").symlink_to(outside)

    with pytest.raises(ValueError, match="network_capability"):
        _ = replay_module().audit_network_capabilities(plugin)


def test_network_capability_audit_rejects_executable_non_python_hook(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    _ = shutil.copytree(PLUGIN, plugin)
    executable = plugin / "hooks" / "fixture-hook.sh"
    _ = executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)

    with pytest.raises(ValueError, match="network_capability"):
        _ = replay_module().audit_network_capabilities(plugin)


def test_network_capability_audit_rejects_hostile_hook_command(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    _ = shutil.copytree(PLUGIN, plugin)
    hooks_path = plugin / "hooks" / "hooks.json"
    hooks = cast("dict[str, object]", json.loads(hooks_path.read_text(encoding="utf-8")))
    groups = cast("dict[str, list[dict[str, object]]]", hooks["hooks"])
    entries = cast("list[dict[str, object]]", groups["PreToolUse"][0]["hooks"])
    entries[0]["command"] = "/usr/bin/curl fixture-target"
    _ = hooks_path.write_text(json.dumps(hooks), encoding="utf-8")

    with pytest.raises(ValueError, match="network_capability"):
        _ = replay_module().audit_network_capabilities(plugin)
