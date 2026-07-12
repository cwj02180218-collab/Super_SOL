import sys
from pathlib import Path

HOOKS_ROOT = Path(__file__).parents[2] / "plugins" / "super-sol" / "hooks"
sys.path.insert(0, str(HOOKS_ROOT))

from super_sol_routes import REPAIR_CONTEXT, Route, context_for, route_prompt  # noqa: E402


def test_unambiguous_prompts_select_one_specialist_route() -> None:
    cases: dict[str, Route] = {
        "Concurrent refresh calls must share one task and propagate cancellation": (
            Route.CONCURRENCY_STATE
        ),
        "Reject path traversal and symlink parents before extracting files": (
            Route.SECURITY_BOUNDARY
        ),
        "Migrate v1 and v2 records to schema v3 idempotently": (
            Route.MIGRATION_COMPATIBILITY
        ),
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
