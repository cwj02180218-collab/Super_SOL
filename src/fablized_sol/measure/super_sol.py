"""Super Sol profile that merges GPT.C positioning with strict harness evidence."""

from dataclasses import dataclass
from typing import Final, Literal

type DecisionStatus = Literal["adopt_now", "park_for_evidence", "reject"]


@dataclass(frozen=True, slots=True)
class SuperSolDecision:
    """One durable policy decision inherited from the GPT.C comparison pass."""

    name: str
    status: DecisionStatus
    rationale: str


@dataclass(frozen=True, slots=True)
class SuperSolProfile:
    """Merged benchmark profile for GPT.C-aligned Fablized SOL runs."""

    name: str
    version: str
    product_surface: str
    model_comparator_surface: str
    reference_surface: str
    adopt_now: tuple[SuperSolDecision, ...]
    park_for_evidence: tuple[SuperSolDecision, ...]
    reject: tuple[SuperSolDecision, ...]


SUPER_SOL_PROFILE: Final = SuperSolProfile(
    name="super-sol",
    version="2026-07-11",
    product_surface="gpt-5.5 + fablized-sol",
    model_comparator_surface="gpt-5.6-sol + fablized-sol",
    reference_surface="GPT.C + Codex CLI",
    adopt_now=(
        SuperSolDecision(
            name="verification-after-latest-code-mutation",
            status="adopt_now",
            rationale=(
                "A successful verifier run must be newer than the latest code mutation; "
                "older success cannot support completion."
            ),
        ),
        SuperSolDecision(
            name="digest-pinned-docker-verifier",
            status="adopt_now",
            rationale=(
                "Model-callable verification runs in a local, immutable, no-network "
                "Docker image rather than the parent process environment."
            ),
        ),
        SuperSolDecision(
            name="out-of-band-bool-only-grader",
            status="adopt_now",
            rationale=(
                "A distinct digest-pinned image grades the final workspace after the model "
                "turn and exposes only pass or fail to the shadow stream."
            ),
        ),
        SuperSolDecision(
            name="typed-local-tool-evidence",
            status="adopt_now",
            rationale=(
                "Only registered local tools returning typed mutation or verification "
                "results receive ledger credit."
            ),
        ),
        SuperSolDecision(
            name="lazy-baseline-first-escalation-analysis",
            status="adopt_now",
            rationale=(
                "Measure GPT-5.5-first routing and escalate only failed or defective tasks "
                "to the GPT-5.6 Sol reference; keep observed cells separate from the "
                "counterfactual cascade."
            ),
        ),
    ),
    park_for_evidence=(
        SuperSolDecision(
            name="promise-without-action-regex",
            status="park_for_evidence",
            rationale=(
                "GPT.C's early-stop regex can be useful as a Codex wrapper heuristic, "
                "but it needs holdout evidence before promotion."
            ),
        ),
        SuperSolDecision(
            name="repeated-failure-disclosure",
            status="park_for_evidence",
            rationale=(
                "Failure-signature disclosure is promising for long Codex loops, but it "
                "is not yet a completion gate."
            ),
        ),
    ),
    reject=(
        SuperSolDecision(
            name="command-output-regex-as-verification-credit",
            status="reject",
            rationale=(
                "Verification credit must come from typed exit status, never from parsed "
                "stdout or model prose."
            ),
        ),
        SuperSolDecision(
            name="fail-open-success",
            status="reject",
            rationale=(
                "Harness parse or verifier setup failures must remain explicit errors, "
                "not apparent successful completions."
            ),
        ),
    ),
)
