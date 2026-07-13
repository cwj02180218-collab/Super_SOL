import sys
from pathlib import Path

HOOKS_ROOT = Path(__file__).parents[2] / "plugins" / "super-sol" / "hooks"
sys.path.insert(0, str(HOOKS_ROOT))

from super_sol_routes import (  # noqa: E402
    REPAIR_CONTEXT,
    Contract,
    Route,
    context_for,
    residual_context,
    route_prompt,
)


def test_action_prompts_select_one_primary_semantic_contract() -> None:
    cases = {
        "Return a deep copy without sharing nested aliases": Contract.OWNERSHIP_ALIASING,
        "Reject unknown commands with usage and the correct return code": (
            Contract.INPUT_ERROR_SEMANTICS
        ),
        "Allow retry after failure without duplicate state": Contract.RETRY_STATE,
        "Fix concurrent refresh cancellation and race conditions": (
            Contract.CONCURRENCY_CANCELLATION
        ),
        "Validate everything before an atomic commit": Contract.FAILURE_ATOMICITY,
        "Migrate v1 records backward-compatibly and reject future versions": (
            Contract.MIGRATION_COMPATIBILITY
        ),
        "Reject path traversal and symlink parents": Contract.SECURITY_PATH_BOUNDARY,
    }

    for prompt, expected in cases.items():
        decision = route_prompt(prompt)
        assert decision.contract is expected
        assert decision.confidence >= 2
        assert 1 <= len(decision.signal_ids) <= 2


def test_equal_contract_scores_are_observe_only() -> None:
    decision = route_prompt(
        "Add path traversal protection and migrate schema versions backward-compatibly"
    )

    assert decision.contract is None
    assert decision.route is Route.PASS_THROUGH
    assert decision.confidence == 0


def test_residual_context_is_bounded_and_does_not_repeat_tests() -> None:
    expected = {
        Contract.OWNERSHIP_ALIASING: (
            "One final semantic check: nested alias isolation. Inspect one untested mutation "
            "path; do not broaden the patch or rerun a passing test."
        ),
        Contract.INPUT_ERROR_SEMANTICS: (
            "One final semantic check: unknown-input exit semantics. Inspect one untested "
            "command; do not broaden the patch or rerun a passing test."
        ),
        Contract.RETRY_STATE: (
            "One final semantic check: retry identity after failure. Inspect one untested "
            "retry result; do not broaden the patch or rerun a passing test."
        ),
        Contract.CONCURRENCY_CANCELLATION: (
            "One final semantic check: cancellation propagation. Inspect one untested awaiting "
            "caller; do not broaden the patch or rerun a passing test."
        ),
        Contract.FAILURE_ATOMICITY: (
            "One final semantic check: all-or-nothing publication. Inspect one untested failed "
            "write; do not broaden the patch or rerun a passing test."
        ),
        Contract.MIGRATION_COMPATIBILITY: (
            "One final semantic check: old/future schema behavior. Inspect one untested version "
            "boundary; do not broaden the patch or rerun a passing test."
        ),
        Contract.SECURITY_PATH_BOUNDARY: (
            "One final semantic check: canonical path containment. Inspect one untested symlink "
            "path; do not broaden the patch or rerun a passing test."
        ),
    }

    assert {contract: residual_context(contract) for contract in Contract} == expected


def test_unambiguous_prompts_select_one_specialist_route() -> None:
    cases: dict[str, Route] = {
        "Concurrent refresh calls must share one task and propagate cancellation": (
            Route.CONCURRENCY_STATE
        ),
        "Reject path traversal and symlink parents before extracting files": (
            Route.SECURITY_BOUNDARY
        ),
        "Migrate v1 and v2 records to schema v3 idempotently": (Route.MIGRATION_COMPATIBILITY),
        "Validate before mutation and roll back an atomic batch": Route.FAILURE_ATOMICITY,
        "동시 요청의 경쟁 상태와 취소 전파를 고쳐줘": Route.CONCURRENCY_STATE,
        "심볼릭 링크와 경로 순회를 차단해줘": Route.SECURITY_BOUNDARY,
    }

    for prompt, expected in cases.items():
        decision = route_prompt(prompt)
        assert decision.route is expected
        assert decision.score >= 2
        assert decision.signal_ids


def test_generic_ambiguous_explanation_and_non_action_pass_through() -> None:
    prompts = (
        "rename this variable",
        "Explain what a race condition and schema migration are",
        "Explain race conditions and fix this refresh bug",
        "Add path traversal protection and migrate schema versions",
        "동시성과 마이그레이션이 무엇인지 설명만 해줘",
    )

    assert all(route_prompt(prompt).route is Route.PASS_THROUGH for prompt in prompts)


def test_exact_first_line_controls_apply_to_the_remaining_request() -> None:
    off = route_prompt("SUPER SOL OFF\nFix concurrent refresh races")
    assert off.route is Route.PASS_THROUGH
    assert off.forced is True

    forced = route_prompt("SUPER SOL ROUTE concurrency_state\nFix the refresh implementation")
    assert forced.route is Route.CONCURRENCY_STATE
    assert forced.forced is True

    invalid = route_prompt("SUPER SOL ROUTE unknown\nFix the refresh implementation")
    assert invalid.route is Route.PASS_THROUGH
    assert invalid.warning is not None

    assert route_prompt("please quote SUPER SOL OFF").forced is False


def test_signal_aliases_count_once_and_unicode_is_normalized() -> None:
    decision = route_prompt("ＲＡＣＥ condition and race condition must be fixed")  # noqa: RUF001

    assert decision.route is Route.CONCURRENCY_STATE
    assert decision.signal_ids.count("concurrency.race") == 1


def test_general_failure_atomicity_meanings_are_detected_without_fixture_terms() -> None:
    prompts = (
        "Fix the operation so it persists nothing unless every destination succeeds",
        "Fix saving so every write succeeds or none persist",
        "Implement staged writes and commit only after all validations succeed",
        "Fix saving to use a temporary file and replace the destination after fsync",
        "Clean up previously written outputs when a later operation fails",
        "Make repeated delivery attempts avoid duplicate side effects",
        "중간 단계가 실패하면 앞서 저장한 결과도 정리하도록 고쳐줘",
        "모든 검증이 성공한 뒤에만 변경을 반영하도록 구현해줘",
    )

    assert all(route_prompt(prompt).route is Route.FAILURE_ATOMICITY for prompt in prompts)


def test_generic_retry_and_configuration_requests_do_not_imply_atomicity() -> None:
    prompts = (
        "Implement exponential backoff for HTTP retries",
        "Fix configuration precedence between environment and file settings",
        "Update the command help for retry options",
    )

    assert all(route_prompt(prompt).route is Route.PASS_THROUGH for prompt in prompts)


def test_packs_are_exact_bounded_and_never_reference_benchmarks() -> None:
    for route in Route:
        context = context_for(route)
        if route is Route.PASS_THROUGH:
            assert context is None
            continue
        assert context is not None
        assert len(context.split()) <= 90
        assert "T102" not in context
        assert "Terra" not in context
        assert "Sol" not in context

    assert REPAIR_CONTEXT == (
        "Verification failed. Use only the observed failure to revisit the active route "
        "invariants, make the smallest correction, and rerun the same focused verification once."
    )
