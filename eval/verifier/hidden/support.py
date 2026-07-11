import json
import os
import subprocess
from typing import cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


def _drop_privileges() -> None:
    os.setgid(65534)
    os.setuid(65534)


def call_subject(request: dict[str, JsonValue]) -> dict[str, JsonValue]:
    process = subprocess.run(
        ("/usr/local/bin/python", "/usr/local/bin/grader-subject"),
        input=json.dumps(request),
        capture_output=True,
        check=False,
        text=True,
        cwd="/workspace",
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        preexec_fn=_drop_privileges,
    )
    assert process.returncode == 0, process.stderr
    response = cast("JsonValue", json.loads(process.stdout))
    if not isinstance(response, dict):
        raise TypeError
    return response
