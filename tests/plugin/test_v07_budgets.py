import json
import os
import statistics
import subprocess
import time
from pathlib import Path

from super_sol_routes import CONTEXT_CODEPOINT_LIMIT, REPAIR_CONTEXT, Contract, residual_context
from super_sol_state import MAX_INJECTIONS_PER_TURN

from .conftest import HOOK_SCRIPT, PLUGIN_ROOT, HookRunner, hook_input


def test_public_context_and_injection_budgets_are_frozen() -> None:
    assert CONTEXT_CODEPOINT_LIMIT == 180
    assert len(REPAIR_CONTEXT) <= CONTEXT_CODEPOINT_LIMIT
    assert MAX_INJECTIONS_PER_TURN == 1
    assert all(len(residual_context(contract)) <= CONTEXT_CODEPOINT_LIMIT for contract in Contract)


def _measure_process(
    command: list[str], payload: str, environment: dict[str, str], count: int
) -> float:
    elapsed_ms: list[float] = []
    for _index in range(count):
        started = time.perf_counter()
        completed = subprocess.run(  # noqa: S603
            command,
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        elapsed_ms.append((time.perf_counter() - started) * 1000)
        assert completed.returncode == 0
    return statistics.quantiles(elapsed_ms, n=100, method="inclusive")[94]


def test_local_prompt_hook_has_bounded_absolute_and_incremental_p95(
    plugin_data: Path,
) -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PLUGIN_DATA": str(plugin_data),
        "PLUGIN_ROOT": str(PLUGIN_ROOT),
        "PYTHONUTF8": "1",
    }
    payload = json.dumps(hook_input("UserPromptSubmit", prompt="rename this variable"))
    hook_p95 = _measure_process(
        ["/usr/bin/python3", "-S", str(HOOK_SCRIPT)], payload, environment, 200
    )
    floor_p95 = _measure_process(["/usr/bin/python3", "-S", "-c", ""], "", environment, 100)

    assert hook_p95 < 125, hook_p95
    assert hook_p95 - floor_p95 < 90, (hook_p95, floor_p95)


def test_stored_state_is_bounded_and_contains_no_raw_fixture_text(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "Fix concurrent refresh cancellation and race conditions SECRET_PROMPT"
    command = "uv run pytest -q SECRET_COMMAND"
    source = "SECRET_SOURCE"
    output = "SECRET_OUTPUT"
    assert run_hook(hook_input("UserPromptSubmit", prompt=prompt)).stdout is None
    assert (
        run_hook(
            hook_input(
                "PostToolUse",
                tool_name="Write",
                tool_use_id="budget-edit",
                tool_input={"content": source, "file_path": "SECRET_FILE"},
                tool_response={"success": True},
            )
        ).stdout
        is None
    )
    verification = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="budget-verification",
            tool_input={"command": command},
            tool_response={"exit_code": 0, "output": output},
        )
    )
    assert verification.stdout is not None

    files = [path for path in plugin_data.rglob("*") if path.is_file()]
    assert files
    assert all(path.stat().st_size <= 4096 for path in files)
    stored = "".join(path.read_text(encoding="utf-8") for path in files)
    for secret in (prompt, command, source, output, "SECRET_FILE"):
        assert secret not in stored
