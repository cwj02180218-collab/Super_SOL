import re
from pathlib import Path

import pytest

from fablized_sol.eval.supply_chain import (
    BASE_IMAGE,
    SupplyChainPolicyError,
    build_audit_commands,
    validate_pinned_base,
)

_EXPECTED_BASE = (
    "python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df"
)


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


def test_container_security_workflow_pins_actions_and_gates_both_images() -> None:
    workflow = Path(".github/workflows/container-security.yml").read_text(encoding="utf-8")
    action_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]

    assert action_lines
    assert all(re.search(r"@[0-9a-f]{40}(?:\s|$)", line) for line in action_lines)
    assert workflow.count("command: cves") == 2
    assert workflow.count("command: sbom") == 2
    assert workflow.count("exit-code: true") == 2
    assert workflow.count("only-severities: critical,high") == 2
