"""Installed-package surface smoke tests."""

from importlib.metadata import distribution, entry_points
from pathlib import Path
from tomllib import load
from typing import TypedDict

from pydantic import TypeAdapter

import fablized_sol


class _SdistConfig(TypedDict):
    include: list[str]


class _TargetsConfig(TypedDict):
    sdist: _SdistConfig


class _BuildConfig(TypedDict):
    targets: _TargetsConfig


class _HatchConfig(TypedDict):
    build: _BuildConfig


class _ToolConfig(TypedDict):
    hatch: _HatchConfig


class _ProjectConfig(TypedDict):
    tool: _ToolConfig


_PROJECT_ADAPTER = TypeAdapter[_ProjectConfig](_ProjectConfig)


def test_console_scripts_are_registered() -> None:
    # Given the project is installed in the uv environment
    expected = {
        "fablized-sol-eval",
        "fablized-sol-report",
        "super-sol-eval",
        "super-sol-report",
        "super-sol-container-audit",
        "super-sol-codex-ab",
        "super-sol-codex-ab-report",
        "super-sol-codex-ab-audit",
    }

    # When its public console-script metadata is selected
    scripts = {script.name for script in entry_points(group="console_scripts")}

    # Then primary and compatibility entry points are registered
    assert expected <= scripts


def test_distribution_uses_super_sol_name() -> None:
    # Given the project is installed in the uv environment
    # When callers inspect its distribution metadata
    name = distribution("super-sol-harness").metadata["Name"]

    # Then the public package uses the Super SOL distribution name
    assert name == "super-sol-harness"


def test_distribution_declares_mit_license() -> None:
    # Given the installed Super SOL distribution
    # When its core metadata is inspected
    license_expression = distribution("super-sol-harness").metadata["License-Expression"]

    # Then downstream users receive a machine-readable MIT license
    assert license_expression == "MIT"


def test_package_exports_version() -> None:
    # Given the project is installed in the uv environment
    # When callers inspect its public package metadata
    version = fablized_sol.__version__

    # Then the package exports the distribution version
    assert version == "0.5.0rc1"


def test_sdist_uses_an_explicit_source_allowlist() -> None:
    # Given the package build configuration
    with Path("pyproject.toml").open("rb") as stream:
        configuration = _PROJECT_ADAPTER.validate_python(load(stream))

    # When the sdist file selection is inspected
    included = set(configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])

    # Then only publishable source and project metadata roots are eligible
    assert included == {
        "/.python-version",
        "/.agents",
        "/AGENTS.md",
        "/CONTRIBUTING.md",
        "/LICENSE",
        "/NOTICE",
        "/README.md",
        "/SECURITY.md",
        "/benchmarks",
        "/docs",
        "/eval",
        "/pyproject.toml",
        "/plugins",
        "/security",
        "/src",
        "/tests",
        "/uv.lock",
    }


def test_readme_exposes_beginner_plugin_and_current_model_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.3.1" in readme
    assert "추가 API 과금 호출 없음" in readme
    assert "gpt-5.6-terra" in readme
    assert "--product-effort" in readme
    assert "--confirm-billable" in readme
    assert "super-sol-container-audit" in readme
    assert "https://openai.com/index/gpt-5-6/" in readme
    assert "GPT-5.6 Sol is a limited preview" not in readme
    assert "v0.3.1 remains the stable release" in readme
    assert "super-sol-codex-ab" in readme
    assert "unseen holdout" in readme


def test_v05_release_candidate_docs_freeze_cells_and_claim_boundary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    postmortem = Path("docs/BENCHMARK_POSTMORTEM_0.4.md").read_text(encoding="utf-8")
    protocol = Path("docs/V0.5_PERFORMANCE_PROTOCOL.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{postmortem}\n{protocol}"

    for expected in (
        "terra-raw",
        "terra-v05",
        "sol-high-raw",
        "sol-max-raw",
        "+5",
        "-2",
        "1.15",
        "0.5.0rc1",
        "v0.3.1 remains the stable release",
    ):
        assert expected in combined

    assert "72 paid slots" in postmortem
    assert "+26.86%" in postmortem
    assert "+30.86%" in postmortem
    assert "-0.50%" in postmortem
    assert "+11.08%" in postmortem
    assert "T109-T116" in protocol
    assert "T117-T124" in protocol
    assert "universal Pro equivalence" in protocol
