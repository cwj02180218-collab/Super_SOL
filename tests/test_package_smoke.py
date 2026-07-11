"""Installed-package surface smoke tests."""

from importlib.metadata import entry_points
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


def test_console_script_is_registered() -> None:
    # Given the project is installed in the uv environment
    # When its console-script metadata is selected
    scripts = entry_points(group="console_scripts", name="fablized-sol-eval")

    # Then exactly one public CLI entry point is registered
    assert len(scripts) == 1


def test_package_exports_version() -> None:
    # Given the project is installed in the uv environment
    # When callers inspect its public package metadata
    version = fablized_sol.__version__

    # Then the package exports the distribution version
    assert version == "0.1.0"


def test_sdist_uses_an_explicit_source_allowlist() -> None:
    # Given the package build configuration
    with Path("pyproject.toml").open("rb") as stream:
        configuration = _PROJECT_ADAPTER.validate_python(load(stream))

    # When the sdist file selection is inspected
    included = set(configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])

    # Then only publishable source and project metadata roots are eligible
    assert included == {
        "/.python-version",
        "/AGENTS.md",
        "/README.md",
        "/docs",
        "/eval",
        "/pyproject.toml",
        "/src",
        "/tests",
        "/uv.lock",
    }
