import pytest

from fablized_sol.engine.goals import (
    DuplicateGoalIdError,
    Evidence,
    Goal,
    GoalBook,
    GoalId,
    GoalStatus,
    InvalidGoalTransitionError,
    MissingEvidenceError,
    VerificationGoalError,
    VerifyCommand,
)


def one_goal_book() -> GoalBook:
    return GoalBook.create(
        brief="Ship the parser",
        goals=(Goal(GoalId("G001"), "Implement parser", "Parse valid input"),),
    )


def verification_goal_book() -> GoalBook:
    return GoalBook.create(
        brief="Ship verified code",
        goals=(
            Goal(GoalId("G001"), "Implement parser", "Parse valid input"),
            Goal(GoalId("G002"), "Verify parser", "Run the focused tests"),
        ),
    )


def test_create_rejects_duplicate_goal_ids() -> None:
    # Given
    goals = (
        Goal(GoalId("G001"), "First", "First objective"),
        Goal(GoalId("G001"), "Second", "Second objective"),
    )

    # When / Then
    with pytest.raises(DuplicateGoalIdError, match="G001"):
        _ = GoalBook.create(brief="Duplicate story", goals=goals)


@pytest.mark.parametrize("evidence", ["", "   ", "\n\t"], ids=["empty", "spaces", "whitespace"])
def test_completion_requires_non_blank_evidence(evidence: str) -> None:
    # Given
    book = one_goal_book()

    # When / Then
    with pytest.raises(MissingEvidenceError, match="G001"):
        _ = book.complete(GoalId("G001"), Evidence(evidence))


@pytest.mark.parametrize(
    "verify_cmd",
    [None, VerifyCommand(""), VerifyCommand("  ")],
    ids=["missing", "empty", "whitespace"],
)
def test_final_goal_requires_non_blank_verification_command(
    verify_cmd: VerifyCommand | None,
) -> None:
    # Given
    book = verification_goal_book()

    # When / Then
    with pytest.raises(VerificationGoalError, match="G002"):
        _ = book.complete(GoalId("G002"), Evidence("pytest passed"), verify_cmd)


def test_completion_returns_new_book_without_mutating_original() -> None:
    # Given
    book = one_goal_book()

    # When
    updated = book.complete(GoalId("G001"), Evidence("test_x passed"), VerifyCommand("pytest"))

    # Then
    assert book.goals[0].status is GoalStatus.PENDING
    assert book.goals[0].evidence is None
    assert updated.goals[0] == Goal(
        GoalId("G001"),
        "Implement parser",
        "Parse valid input",
        status=GoalStatus.COMPLETE,
        evidence=Evidence("test_x passed"),
        verify_cmd=VerifyCommand("pytest"),
    )


def test_completion_replaces_only_matching_goal() -> None:
    # Given
    book = verification_goal_book()
    untouched_goal = book.goals[1]

    # When
    updated = book.complete(GoalId("G001"), Evidence("test_parser passed"))

    # Then
    assert updated.goals[0].status is GoalStatus.COMPLETE
    assert updated.goals[1] is untouched_goal


def test_completion_rejects_unknown_goal() -> None:
    # Given
    book = one_goal_book()

    # When / Then
    with pytest.raises(InvalidGoalTransitionError, match="G999"):
        _ = book.complete(GoalId("G999"), Evidence("evidence"))


def test_completion_rejects_terminal_goal() -> None:
    # Given
    completed = one_goal_book().complete(
        GoalId("G001"),
        Evidence("pytest passed"),
        VerifyCommand("pytest"),
    )

    # When / Then
    with pytest.raises(InvalidGoalTransitionError, match="complete"):
        _ = completed.complete(
            GoalId("G001"),
            Evidence("pytest passed again"),
            VerifyCommand("pytest"),
        )


def test_final_goal_records_verification_command_and_evidence() -> None:
    # Given
    book = verification_goal_book()

    # When
    updated = book.complete(
        GoalId("G002"),
        Evidence("12 tests passed"),
        VerifyCommand("uv run pytest"),
    )

    # Then
    assert updated.goals[1].status is GoalStatus.COMPLETE
    assert updated.goals[1].evidence == Evidence("12 tests passed")
    assert updated.goals[1].verify_cmd == VerifyCommand("uv run pytest")
