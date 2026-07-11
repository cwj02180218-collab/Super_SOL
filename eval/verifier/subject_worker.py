import importlib
import json
import sys
from pathlib import Path
from typing import Protocol, cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type Argument = JsonValue | Path
_SUBJECT_ERRORS = (Exception,)


class SubjectCallable(Protocol):
    def __call__(self, *args: Argument) -> JsonValue: ...


class SubjectFactory(Protocol):
    def __call__(self) -> Argument: ...


def _mapping(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError
    return value


def _list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _function(request: dict[str, JsonValue]) -> JsonValue:
    module = importlib.import_module(_string(request["module"]))
    function = cast("SubjectCallable", getattr(module, _string(request["name"])))
    args: list[Argument] = list(_list(request["args"]))
    for raw_index in _list(request.get("path_args", [])):
        if not isinstance(raw_index, int) or isinstance(raw_index, bool):
            raise TypeError
        args[raw_index] = Path(str(args[raw_index]))
    return function(*args)


def _sequence(request: dict[str, JsonValue]) -> list[JsonValue]:
    module = importlib.import_module(_string(request["module"]))
    factory = cast("SubjectFactory", getattr(module, _string(request["name"])))
    instance = factory()
    results: list[JsonValue] = []
    for raw_call in _list(request["calls"]):
        call = _list(raw_call)
        if len(call) != 2:
            raise ValueError
        method = cast("SubjectCallable", getattr(instance, _string(call[0])))
        results.append(method(*_list(call[1])))
    return results


def main() -> int:
    sys.path.insert(0, "/workspace")
    try:
        raw_request = cast("JsonValue", json.loads(sys.stdin.read()))
        request = _mapping(raw_request)
        kind = _string(request["kind"])
        if kind == "function":
            result = _function(request)
        elif kind == "sequence":
            result = _sequence(request)
        else:
            raise ValueError
    except _SUBJECT_ERRORS as error:
        _ = sys.stdout.write(json.dumps({"ok": False, "error": type(error).__name__}) + "\n")
        return 0
    _ = sys.stdout.write(json.dumps({"ok": True, "result": result}, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
