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
    assert version == "0.2.1"


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
        "/CONTRIBUTING.md",
        "/LICENSE",
        "/NOTICE",
        "/README.md",
        "/SECURITY.md",
        "/benchmarks",
        "/docs",
        "/eval",
        "/pyproject.toml",
        "/src",
        "/tests",
        "/uv.lock",
    }
