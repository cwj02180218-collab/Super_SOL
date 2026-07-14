from pathlib import Path

_OFFICIAL_COVERAGE = (
    "uv run pytest --cov=src --cov=plugins/super-sol/hooks "
    "--cov-report=term-missing --cov-fail-under=90"
)
_OFFICIAL_LATENCY = "uv run super-sol-hook-latency --plugin-root plugins/super-sol --output <fresh>"


def test_official_coverage_command_is_frozen_across_release_surfaces() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    plan = Path("docs/superpowers/plans/2026-07-14-super-sol-v0.9-loop-fuse.md").read_text(
        encoding="utf-8"
    )
    report = Path(".superpowers/sdd/v09-latency-gate-report.md").read_text(encoding="utf-8")

    assert _OFFICIAL_COVERAGE in readme
    assert f"- run: {_OFFICIAL_COVERAGE}" in workflow
    assert _OFFICIAL_COVERAGE in plan
    assert _OFFICIAL_COVERAGE in report


def test_latency_gate_is_frozen_and_separate_from_default_ci() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    plan = Path("docs/superpowers/plans/2026-07-14-super-sol-v0.9-loop-fuse.md").read_text(
        encoding="utf-8"
    )
    report = Path(".superpowers/sdd/v09-latency-gate-report.md").read_text(encoding="utf-8")

    assert _OFFICIAL_LATENCY in readme
    assert _OFFICIAL_LATENCY in plan
    assert _OFFICIAL_LATENCY in report
    assert "super-sol-hook-latency" not in workflow
