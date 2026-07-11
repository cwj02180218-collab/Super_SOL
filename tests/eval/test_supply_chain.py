import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fablized_sol.eval.supply_chain import (
    BASE_IMAGE,
    SupplyChainPolicyError,
    app,
    build_audit_commands,
    run_audit,
    validate_pinned_base,
)

_EXPECTED_BASE = (
    "python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df"
)
_RUNNER = CliRunner()


@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.grader"])
def test_verifier_dockerfiles_use_reviewed_multiplatform_digest(name: str) -> None:
    path = Path("eval/verifier") / name

    assert BASE_IMAGE == _EXPECTED_BASE
    assert validate_pinned_base(path) == _EXPECTED_BASE


def test_supply_chain_policy_rejects_mutable_or_wrong_base(tmp_path: Path) -> None:
    mutable = tmp_path / "Dockerfile.mutable"
    wrong = tmp_path / "Dockerfile.wrong"
    _ = mutable.write_text("FROM python:3.12-alpine\n", encoding="utf-8")
    _ = wrong.write_text("FROM node:24-alpine@sha256:" + "a" * 64 + "\n", encoding="utf-8")

    for path in (mutable, wrong):
        with pytest.raises(SupplyChainPolicyError):
            _ = validate_pinned_base(path)


def test_supply_chain_policy_rejects_case_insensitive_extra_stage(tmp_path: Path) -> None:
    path = tmp_path / "Dockerfile"
    _ = path.write_text(
        f"FROM {_EXPECTED_BASE}\nfrom malicious.example/base@sha256:{'c' * 64}\n",
        encoding="utf-8",
    )

    with pytest.raises(SupplyChainPolicyError):
        _ = validate_pinned_base(path)


@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.grader"])
def test_verifier_dependencies_are_hash_locked(name: str) -> None:
    dockerfile = (Path("eval/verifier") / name).read_text(encoding="utf-8")
    lock = Path("eval/verifier/requirements.lock").read_text(encoding="utf-8")

    assert "requirements.lock" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "pytest==9.1.1" in lock
    assert "--hash=sha256:" in lock


def test_audit_plan_builds_scans_and_writes_two_spdx_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    sbom_dir = repo_root / "security" / "sbom"

    commands = build_audit_commands(repo_root, sbom_dir)

    builds = [command for command in commands if command[:2] == ("docker", "build")]
    scans = [command for command in commands if command[:3] == ("docker", "scout", "cves")]
    sboms = [command for command in commands if command[:3] == ("docker", "scout", "sbom")]
    assert len(builds) == 2
    assert {command[command.index("--file") + 1] for command in builds} == {
        "eval/verifier/Dockerfile",
        "eval/verifier/Dockerfile.grader",
    }
    assert len(scans) == 2
    assert all("--only-severity" in command for command in scans)
    assert all("critical,high" in command for command in scans)
    assert all("--exit-code" in command for command in scans)
    assert len(sboms) == 2
    assert {Path(command[command.index("--output") + 1]).name for command in sboms} == {
        "verifier.spdx.json",
        "grader.spdx.json",
    }
    assert max(commands.index(command) for command in sboms) < min(
        commands.index(command) for command in scans
    )


def test_audit_retains_both_scan_results_before_returning_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, ...]] = []

    def fake_run(
        command: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        observed.append(command)
        is_scan = command[:3] == ("docker", "scout", "cves")
        return subprocess.CompletedProcess(command, 9 if is_scan else 0)

    monkeypatch.setattr("fablized_sol.eval.supply_chain.subprocess.run", fake_run)

    assert run_audit(Path.cwd(), tmp_path / "sbom") == 9
    assert sum(command[:3] == ("docker", "scout", "cves") for command in observed) == 2
    assert sum(command[:3] == ("docker", "scout", "sbom") for command in observed) == 2


def test_audit_cli_reports_output_directory_error_without_traceback(tmp_path: Path) -> None:
    file_parent = tmp_path / "file"
    _ = file_parent.write_text("not a directory", encoding="utf-8")

    result = _RUNNER.invoke(
        app,
        ["--repo-root", ".", "--sbom-dir", str(file_parent / "sbom")],
    )

    assert result.exit_code != 0
    assert "could not create SBOM directory" in result.output
    assert "Traceback" not in result.output


def test_container_security_workflow_pins_actions_and_gates_both_images() -> None:
    workflow = Path(".github/workflows/container-security.yml").read_text(encoding="utf-8")
    action_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]

    assert action_lines
    assert all(re.search(r"@[0-9a-f]{40}(?:\s|$)", line) for line in action_lines)
    assert workflow.count("uses: anchore/sbom-action@") == 2
    assert workflow.count("uses: aquasecurity/trivy-action@") == 2
    assert workflow.count("format: spdx-json") == 2
    assert workflow.count("exit-code: 1") == 2
    assert workflow.count("severity: CRITICAL,HIGH") == 2
    assert workflow.find("Generate verifier SBOM") < workflow.find("Scan verifier")
    assert workflow.count("continue-on-error: true") == 2
    assert "Enforce scan gate" in workflow
    assert "if: always()" in workflow
