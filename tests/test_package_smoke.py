"""Installed-package surface smoke tests."""

from importlib.metadata import entry_points

import fablized_sol


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
