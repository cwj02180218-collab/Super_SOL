import subprocess
import sys
from pathlib import Path

import pytest

from fablized_sol.eval import hook_latency_report
from fablized_sol.eval.hook_latency import (
    ABSOLUTE_P95_THRESHOLD_MS,
    DEFAULT_FLOOR_SAMPLES,
    DEFAULT_HOOK_SAMPLES,
    INCREMENTAL_P95_THRESHOLD_MS,
    GateOptions,
    HookLatencyError,
    ProcessResult,
    collect_latency,
    main,
    percentile,
    select_prompt_command,
)

from .hook_latency_test_support import EXACT_COMMAND, plugin_root


def test_select_prompt_command_requires_exact_shipped_argv(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)

    assert select_prompt_command(root) == (
        "/usr/bin/python3",
        "-S",
        str(root / "hooks" / "prompt_dispatcher.py"),
    )


@pytest.mark.parametrize(
    "command",
    [
        '/usr/bin/true -S "$PLUGIN_ROOT/hooks/prompt_dispatcher.py"',
        '/usr/local/bin/python3 -S "$PLUGIN_ROOT/hooks/prompt_dispatcher.py"',
        '/usr/bin/python3 -S "$PLUGIN_ROOT/hooks/alternate.py"',
        EXACT_COMMAND + " extra",
    ],
)
def test_select_prompt_command_rejects_alternate_argv(tmp_path: Path, command: str) -> None:
    root = plugin_root(tmp_path, command)
    _ = (root / "hooks" / "alternate.py").write_text("", encoding="utf-8")

    with pytest.raises(HookLatencyError):
        _ = select_prompt_command(root)


@pytest.mark.parametrize("timeout", [0, 4, 6, "5", True, None])
def test_select_prompt_command_rejects_non_shipped_timeout(
    tmp_path: Path, timeout: int | str | bool | None
) -> None:
    with pytest.raises(HookLatencyError):
        _ = select_prompt_command(plugin_root(tmp_path, timeout=timeout))


def test_select_prompt_command_rejects_symlinked_dispatcher(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)
    dispatcher = root / "hooks" / "prompt_dispatcher.py"
    target = root / "hooks" / "target.py"
    _ = target.write_text("", encoding="utf-8")
    dispatcher.unlink()
    dispatcher.symlink_to(target)

    with pytest.raises(HookLatencyError):
        _ = select_prompt_command(root)


def test_collect_latency_interleaves_two_hooks_with_one_floor_and_uses_allowed_env(
    tmp_path: Path,
) -> None:
    root = plugin_root(tmp_path)
    calls: list[tuple[tuple[str, ...], str, dict[str, str]]] = []
    moments = iter((0.0, 0.01, 0.01, 0.03, 0.03, 0.035, 0.035, 0.045, 0.045, 0.06, 0.06, 0.066))

    def fake_clock() -> float:
        return next(moments)

    def fake_run(
        command: tuple[str, ...], payload: str, environment: dict[str, str]
    ) -> ProcessResult:
        calls.append((command, payload, environment))
        return ProcessResult(returncode=0, stderr="")

    observed = collect_latency(
        GateOptions(root, hook_samples=4, floor_samples=2),
        fake_run,
        fake_clock,
        {"PATH": "/bin", "OPENAI_API_KEY": "not-allowed"},
    )

    assert [call[1] for call in calls] == [
        observed.payload,
        observed.payload,
        "",
        observed.payload,
        observed.payload,
        "",
    ]
    assert observed.hook_samples == pytest.approx((10.0, 20.0, 10.0, 15.0))
    assert observed.floor_samples == pytest.approx((5.0, 6.0))
    assert hook_latency_report.paired_incremental_samples(observed) == pytest.approx(
        (5.0, 15.0, 4.0, 9.0)
    )
    assert all(
        set(environment) == {"PATH", "PLUGIN_DATA", "PLUGIN_ROOT", "PYTHONUTF8"}
        for _, _, environment in calls
    )


def test_percentile_uses_inclusive_linear_interpolation() -> None:
    assert percentile((0.0, 10.0, 20.0, 30.0), 95) == 28.5
    assert percentile((0.0, 10.0, 20.0, 30.0), 50) == 15.0


def test_collect_latency_rejects_nonzero_child_process(tmp_path: Path) -> None:
    def failing_run(
        _command: tuple[str, ...], _payload: str, _environment: dict[str, str]
    ) -> ProcessResult:
        return ProcessResult(returncode=9, stderr="child failed")

    with pytest.raises(HookLatencyError, match="child failed"):
        _ = collect_latency(
            GateOptions(plugin_root(tmp_path), 2, 1), failing_run, clock=lambda: 0.0
        )


def test_hanging_child_exits_two_without_final_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"

    def hanging_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] == 5
        raise subprocess.TimeoutExpired(command, 5)

    monkeypatch.setattr("fablized_sol.eval.hook_latency.subprocess.run", hanging_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["super-sol-hook-latency", "--plugin-root", str(root), "--output", str(output)],
    )

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2
    assert not output.exists()


def test_cli_help_exposes_no_weakening_flags(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["super-sol-hook-latency", "--help"])

    with pytest.raises(SystemExit) as raised:
        main()

    help_text = capsys.readouterr().out
    assert raised.value.code == 0
    assert "--plugin-root" in help_text
    assert "--output" in help_text
    for forbidden in (
        "--hook-samples",
        "--floor-samples",
        "--absolute-threshold-ms",
        "--incremental-threshold-ms",
    ):
        assert forbidden not in help_text


@pytest.mark.parametrize(("passed", "expected_exit"), [(True, 0), (False, 1)])
def test_main_exits_from_the_written_gate_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    passed: bool,
    expected_exit: int,
) -> None:
    def fake_run_and_write(_options: GateOptions, _output: Path) -> bool:
        return passed

    monkeypatch.setattr("fablized_sol.eval.hook_latency.run_and_write", fake_run_and_write)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "super-sol-hook-latency",
            "--plugin-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == expected_exit


def test_latency_defaults_remain_frozen() -> None:
    assert DEFAULT_HOOK_SAMPLES == 300
    assert DEFAULT_FLOOR_SAMPLES == 150
    assert ABSOLUTE_P95_THRESHOLD_MS == 100.0
    assert INCREMENTAL_P95_THRESHOLD_MS == 70.0
