from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE


def test_super_sol_profile_keeps_product_and_reference_surfaces_separate() -> None:
    # Given the merged Super Sol profile
    profile = SUPER_SOL_PROFILE

    # When its benchmark claim boundaries are inspected
    # Then the harness product and Codex reference comparator are not conflated
    assert profile.name == "super-sol"
    assert profile.product_surface == "gpt-5.5 + fablized-sol"
    assert profile.model_comparator_surface == "gpt-5.6-sol + fablized-sol"
    assert profile.reference_surface == "GPT.C + Codex CLI"


def test_super_sol_profile_promotes_strict_evidence_and_parks_text_heuristics() -> None:
    # Given the merged Super Sol profile
    adopted = {decision.name for decision in SUPER_SOL_PROFILE.adopt_now}
    parked = {decision.name for decision in SUPER_SOL_PROFILE.park_for_evidence}
    rejected = {decision.name for decision in SUPER_SOL_PROFILE.reject}

    # When its decision table is inspected
    # Then strict evidence becomes policy while GPT.C's weaker heuristics stay experimental
    assert "verification-after-latest-code-mutation" in adopted
    assert "digest-pinned-docker-verifier" in adopted
    assert "out-of-band-bool-only-grader" in adopted
    assert "lazy-baseline-first-escalation-analysis" in adopted
    assert "promise-without-action-regex" in parked
    assert "command-output-regex-as-verification-credit" in rejected
