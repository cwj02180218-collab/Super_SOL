"""Source and wheel archive contract tests."""

from pathlib import Path
from tomllib import load

from tests.package_smoke_support import (
    JSON_OBJECT_ADAPTER,
    PROJECT_ADAPTER,
    RELEASE_ASSET_MAP,
    STRING_MAP_ADAPTER,
    WHEEL_ASSET_ROOT,
    archive_members,
    forbidden_members,
    fresh_archives,
    nested_object,
)


def test_sdist_uses_an_explicit_source_allowlist() -> None:
    with Path("pyproject.toml").open("rb") as stream:
        configuration = PROJECT_ADAPTER.validate_python(load(stream))

    included = set(configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])

    assert included == {
        "/.python-version",
        "/.agents",
        "/AGENTS.md",
        "/CONTRIBUTING.md",
        "/LICENSE",
        "/NOTICE",
        "/README.md",
        "/SECURITY.md",
        "/benchmarks/v0.9-loop-replay/README.md",
        "/benchmarks/v0.9-loop-replay/report.json",
        "/docs",
        "/eval/v09_loop*",
        "/pyproject.toml",
        "/plugins/super-sol/.codex-plugin/plugin.json",
        "/plugins/super-sol/hooks",
        "/plugins/super-sol/skills/super-sol",
        "/security",
        "/src",
        "/uv.lock",
    }


def test_v09_wheel_release_assets_use_an_explicit_stable_mapping() -> None:
    with Path("pyproject.toml").open("rb") as stream:
        configuration = JSON_OBJECT_ADAPTER.validate_python(load(stream))
    tool = nested_object(configuration["tool"], "tool")
    hatch = nested_object(tool["hatch"], "hatch")
    build = nested_object(hatch["build"], "build")
    targets = nested_object(build["targets"], "targets")
    wheel = nested_object(targets["wheel"], "wheel")
    force_include_value = wheel.get("force-include")

    assert force_include_value is not None
    force_include = STRING_MAP_ADAPTER.validate_python(force_include_value)
    assert force_include == RELEASE_ASSET_MAP
    assert all(Path(source).is_file() for source in force_include)


def test_fresh_wheel_and_sdist_contain_only_publishable_v09_assets(tmp_path: Path) -> None:
    sdist, wheel = fresh_archives(tmp_path)
    sdist_members, wheel_members = archive_members(sdist, wheel)
    allowed_benchmarks = {
        "benchmarks/v0.9-loop-replay/README.md",
        "benchmarks/v0.9-loop-replay/report.json",
    }

    assert set(RELEASE_ASSET_MAP) <= sdist_members
    assert set(RELEASE_ASSET_MAP.values()) <= wheel_members
    assert not forbidden_members(sdist_members)
    assert not forbidden_members(wheel_members)
    assert {member for member in sdist_members if member.startswith("benchmarks/")} == (
        allowed_benchmarks
    )
    assert {
        member.removeprefix(f"{WHEEL_ASSET_ROOT}/")
        for member in wheel_members
        if member.startswith(f"{WHEEL_ASSET_ROOT}/benchmarks/")
    } == allowed_benchmarks
