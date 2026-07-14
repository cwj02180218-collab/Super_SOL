from super_sol_commands import CommandKind, classify_command, command_text


def test_classify_command_normalizes_supported_verifiers() -> None:
    info = classify_command("uv run pytest tests/plugin -q")

    assert info.kind is CommandKind.VERIFIER
    assert info.normalized == "pytest"


def test_classify_command_marks_compound_shell_unknown() -> None:
    info = classify_command("pytest -q && pytest -q")

    assert info.kind is CommandKind.UNKNOWN
    assert info.argv is None


def test_command_text_accepts_command_and_cmd_fields() -> None:
    assert command_text({"tool_input": {"command": "pytest -q"}}) == "pytest -q"
    assert command_text({"tool_input": {"cmd": "go test ./pkg"}}) == "go test ./pkg"
