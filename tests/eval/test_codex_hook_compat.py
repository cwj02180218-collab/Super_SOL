import json
import subprocess
import sys
from pathlib import Path

import pytest

from fablized_sol.eval.codex_hook_compat import (
    REQUIRED_EVENTS,
    HookCompatibility,
    HookCompatibilityError,
    main,
    probe_codex_hooks,
    read_hook_events,
)

_FIXTURE_FAILURE = "fixture failure"


def test_read_hook_events_accepts_complete_schema(tmp_path: Path) -> None:
    bundle = tmp_path / "codex_app_server_protocol.v2.schemas.json"
    _ = bundle.write_text(
        json.dumps({"definitions": {"HookEventName": {"enum": sorted(REQUIRED_EVENTS)}}}),
        encoding="utf-8",
    )

    assert read_hook_events(bundle) == REQUIRED_EVENTS


def test_read_hook_events_reports_missing_event(tmp_path: Path) -> None:
    bundle = tmp_path / "codex_app_server_protocol.v2.schemas.json"
    _ = bundle.write_text(
        '{"definitions":{"HookEventName":{"enum":["preToolUse"]}}}', encoding="utf-8"
    )

    assert read_hook_events(bundle) == frozenset({"preToolUse"})


def test_read_hook_events_finds_nested_dollar_definitions(tmp_path: Path) -> None:
    bundle = tmp_path / "codex_app_server_protocol.v2.schemas.json"
    _ = bundle.write_text(
        json.dumps({"$defs": {"protocol": {"definitions": {"HookEventName": {"enum": ["x"]}}}}}),
        encoding="utf-8",
    )

    assert read_hook_events(bundle) == frozenset({"x"})


def test_read_hook_events_rejects_conflicting_definitions(tmp_path: Path) -> None:
    bundle = tmp_path / "codex_app_server_protocol.v2.schemas.json"
    _ = bundle.write_text(
        json.dumps(
            {
                "definitions": {"HookEventName": {"enum": ["preCompact"]}},
                "$defs": {"HookEventName": {"enum": ["postCompact"]}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(HookCompatibilityError):
        _ = read_hook_events(bundle)


def test_probe_uses_only_version_and_exact_schema_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []
    codex = tmp_path / "codex"

    def fake_run(argv: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[-1] == "--version":
            return subprocess.CompletedProcess(argv, 0, "codex-cli 0.144.0-alpha.4\n", "")
        output = Path(argv[-1])
        output.mkdir()
        _ = (output / "codex_app_server_protocol.v2.schemas.json").write_text(
            json.dumps({"definitions": {"HookEventName": {"enum": sorted(REQUIRED_EVENTS)}}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("fablized_sol.eval.codex_hook_compat.subprocess.run", fake_run)
    codex.touch(mode=0o700)

    observed = probe_codex_hooks(codex)

    assert observed == HookCompatibility(
        codex_version="codex-cli 0.144.0-alpha.4",
        observed_events=REQUIRED_EVENTS,
        missing_events=frozenset(),
        compatible=True,
    )
    assert calls[0] == (str(codex), "--version")
    assert calls[1][:4] == (str(codex), "app-server", "generate-json-schema", "--experimental")
    assert calls[1][4] == "--out"
    assert calls[1][5].endswith("codex_app_server_protocol.v2.schemas.json")
    assert all("exec" not in call for call in calls)


@pytest.mark.parametrize(
    ("compatibility", "expected_exit"),
    [
        (
            HookCompatibility(
                codex_version="codex-cli test",
                observed_events=REQUIRED_EVENTS,
                missing_events=frozenset(),
                compatible=True,
            ),
            0,
        ),
        (
            HookCompatibility(
                codex_version="codex-cli test",
                observed_events=frozenset(),
                missing_events=REQUIRED_EVENTS,
                compatible=False,
            ),
            1,
        ),
    ],
)
def test_main_uses_compatibility_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    compatibility: HookCompatibility,
    expected_exit: int,
) -> None:
    def fake_probe(_codex: Path) -> HookCompatibility:
        return compatibility

    monkeypatch.setattr("fablized_sol.eval.codex_hook_compat.probe_codex_hooks", fake_probe)
    monkeypatch.setattr(sys, "argv", ["super-sol-hook-doctor", "--codex", str(tmp_path / "codex")])

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == expected_exit
    assert json.loads(capsys.readouterr().out)["compatible"] is compatibility.compatible


def test_main_exits_two_for_local_inspection_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def failing_probe(_codex: Path) -> HookCompatibility:
        raise HookCompatibilityError(_FIXTURE_FAILURE)

    monkeypatch.setattr("fablized_sol.eval.codex_hook_compat.probe_codex_hooks", failing_probe)
    monkeypatch.setattr(sys, "argv", ["super-sol-hook-doctor", "--codex", str(tmp_path / "codex")])

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2
    assert json.loads(capsys.readouterr().out)["error"] == _FIXTURE_FAILURE
