"""Immutable classification registry for locally exposed tools."""

from dataclasses import dataclass
from typing import Final, override

from fablized_sol.engine.models import ToolKind, ToolName

_REQUIRED_LOCAL_TOOLS: Final[tuple[ToolName, ...]] = (
    ToolName("list_files"),
    ToolName("read_file"),
    ToolName("write_file"),
    ToolName("run_verification"),
)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One immutable tool-name classification."""

    name: ToolName
    kind: ToolKind


@dataclass(frozen=True, slots=True)
class DuplicateToolError(Exception):
    """A registry specification repeats a tool name."""

    name: ToolName

    @override
    def __str__(self) -> str:
        return f"duplicate tool registry entry: {self.name}"


@dataclass(frozen=True, slots=True)
class UnknownToolError(Exception):
    """An agent exposure references or omits a required local tool."""

    name: ToolName

    @override
    def __str__(self) -> str:
        return f"unknown or omitted local tool: {self.name}"


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    """Tuple-backed registry that cannot change after construction."""

    _specs: tuple[ToolSpec, ...]

    @classmethod
    def create(cls, specs: tuple[ToolSpec, ...]) -> "ToolRegistry":
        """Create a registry while rejecting ambiguous duplicate names."""
        seen: set[ToolName] = set()
        for spec in specs:
            if spec.name in seen:
                raise DuplicateToolError(name=spec.name)
            seen.add(spec.name)
        return cls(_specs=specs)

    def kind_for(self, name: ToolName) -> ToolKind:
        """Return the registered kind or the non-credit-bearing unknown kind."""
        for spec in self._specs:
            if spec.name == name:
                return spec.kind
        return ToolKind.UNKNOWN

    def validate_exposed(self, names: tuple[ToolName, ...]) -> None:
        """Require the complete registered local tool set and no unknown names."""
        for required_name in _REQUIRED_LOCAL_TOOLS:
            if required_name not in names or self.kind_for(required_name) is ToolKind.UNKNOWN:
                raise UnknownToolError(name=required_name)
        for name in names:
            if self.kind_for(name) is ToolKind.UNKNOWN:
                raise UnknownToolError(name=name)
