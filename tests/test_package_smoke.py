"""Installed distribution and public README smoke tests."""

from importlib.metadata import distribution, entry_points
from pathlib import Path

import fablized_sol


def test_console_scripts_are_registered() -> None:
    expected = {
        "fablized-sol-eval",
        "fablized-sol-report",
        "super-sol-eval",
        "super-sol-report",
        "super-sol-container-audit",
        "super-sol-codex-ab",
        "super-sol-codex-ab-report",
        "super-sol-codex-ab-audit",
        "super-sol-hook-latency",
    }

    scripts = {script.name for script in entry_points(group="console_scripts")}

    assert expected <= scripts


def test_distribution_uses_super_sol_name() -> None:
    assert distribution("super-sol-harness").metadata["Name"] == "super-sol-harness"


def test_distribution_declares_mit_license() -> None:
    assert distribution("super-sol-harness").metadata["License-Expression"] == "MIT"


def test_package_exports_version() -> None:
    assert fablized_sol.__version__ == "0.9.1rc1"


def test_readme_exposes_beginner_plugin_and_current_model_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.9.1-rc1" in readme
    assert "추가 API 과금 호출 없음" in readme
    assert "gpt-5.6-terra" in readme
    assert "--product-effort" in readme
    assert "--confirm-billable" in readme
    assert "super-sol-container-audit" in readme
    assert "https://openai.com/index/gpt-5-6/" in readme
    assert "GPT-5.6 Sol is a limited preview" not in readme
    assert "v0.8.0 is the stable release" in readme
    assert "v0.9.1-rc1 is a prerelease" in readme
    assert "super-sol-codex-ab" in readme
    assert "unseen holdout" in readme


def test_readme_exposes_v08_stable_plugin_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    stable_heading = "### 현재 안정판 v0.8.0 설치"

    assert stable_heading in readme
    stable_section = readme.split(stable_heading, maxsplit=1)[1].split(
        "### 새 버전으로 업데이트", maxsplit=1
    )[0]
    assert (
        "codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.8.0" in stable_section
    )
    for hook_event in ("UserPromptSubmit", "PreToolUse", "PostToolUse"):
        assert f"`{hook_event}`" in stable_section
    assert "v0.8.0은 현재 안정판입니다." in stable_section
