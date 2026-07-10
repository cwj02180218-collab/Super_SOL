import pytest

from fablized_sol.engine.models import ToolKind, ToolName
from fablized_sol.harness.registry import (
    DuplicateToolError,
    ToolRegistry,
    ToolSpec,
    UnknownToolError,
)


def _complete_registry() -> ToolRegistry:
    return ToolRegistry.create(
        (
            ToolSpec(ToolName("list_files"), ToolKind.READ),
            ToolSpec(ToolName("read_file"), ToolKind.READ),
            ToolSpec(ToolName("write_file"), ToolKind.MUTATION),
            ToolSpec(ToolName("run_verification"), ToolKind.VERIFICATION),
        )
    )


def test_registry_rejects_duplicate_tool_names() -> None:
    # Given two specifications with the same tool name
    spec = ToolSpec(ToolName("read_file"), ToolKind.READ)

    # When the registry is created, then the ambiguous registry is rejected
    with pytest.raises(DuplicateToolError):
        _ = ToolRegistry.create((spec, spec))


def test_registry_returns_unknown_for_unregistered_runtime_tool() -> None:
    # Given a complete local tool registry
    registry = _complete_registry()

    # When an unexpected runtime tool is classified
    kind = registry.kind_for(ToolName("unexpected"))

    # Then it receives no evidence-bearing kind
    assert kind is ToolKind.UNKNOWN


def test_registry_rejects_an_omitted_required_tool() -> None:
    # Given a complete registry but an incomplete agent exposure list
    registry = _complete_registry()
    exposed = (
        ToolName("list_files"),
        ToolName("read_file"),
        ToolName("write_file"),
    )

    # When the exposure is validated, then the omission is rejected
    with pytest.raises(UnknownToolError):
        registry.validate_exposed(exposed)


def test_registry_rejects_an_unregistered_exposed_tool() -> None:
    # Given all required names plus an unregistered name
    registry = _complete_registry()
    exposed = (
        ToolName("list_files"),
        ToolName("read_file"),
        ToolName("write_file"),
        ToolName("run_verification"),
        ToolName("shell"),
    )

    # When the exposure is validated, then the unknown name is rejected
    with pytest.raises(UnknownToolError):
        registry.validate_exposed(exposed)
