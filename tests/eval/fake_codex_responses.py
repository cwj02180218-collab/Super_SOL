"""Loopback-only fake Responses provider for Codex runtime tests."""

# ruff: noqa: EM101, EM102, TRY003, TRY004

from __future__ import annotations

import json
import select
import subprocess
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, ClassVar, Self, TextIO, cast, override

from pydantic import JsonValue, TypeAdapter

if TYPE_CHECKING:
    from pathlib import Path

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_RESPONSE: dict[str, JsonValue] = {
    "created_at": 0,
    "error": None,
    "id": "resp-local-fixture",
    "incomplete_details": None,
    "instructions": None,
    "max_output_tokens": None,
    "model": "gpt-5.6-sol",
    "object": "response",
    "output": [],
    "parallel_tool_calls": True,
    "previous_response_id": None,
    "reasoning": {"effort": "low", "summary": None},
    "status": "completed",
    "store": False,
    "temperature": 1.0,
    "text": {"format": {"type": "text"}},
    "tool_choice": "auto",
    "tools": [],
    "top_p": 1.0,
    "truncation": "disabled",
    "usage": {
        "input_tokens": 1,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 1,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 2,
    },
}


@dataclass(frozen=True, slots=True)
class RecordedResponseRequest:
    """One accepted fake Responses request."""

    body: dict[str, JsonValue]
    target: str


@dataclass(frozen=True, slots=True)
class AdapterRecord:
    """One terminal-hook record emitted by the temporary local adapter."""

    event: str
    output: dict[str, JsonValue] | None


def read_adapter_records(events: Path) -> tuple[AdapterRecord, ...]:
    """Read ordered event/output records from the local adapter's JSONL log."""
    if not events.exists():
        return ()
    records: list[AdapterRecord] = []
    for line in events.read_text(encoding="utf-8").splitlines():
        record = _OBJECT_ADAPTER.validate_json(line)
        event, output = record.get("event"), record.get("output")
        assert isinstance(event, str)
        assert output is None or isinstance(output, dict)
        records.append(AdapterRecord(event, output))
    return tuple(records)


def is_compaction_request(request: RecordedResponseRequest) -> bool:
    """Identify the current Codex standalone compaction Responses payload."""
    client_metadata = request.body.get("client_metadata")
    if not isinstance(client_metadata, dict):
        return False
    turn_metadata = client_metadata.get("x-codex-turn-metadata")
    if not isinstance(turn_metadata, str):
        return False
    metadata = _OBJECT_ADAPTER.validate_json(turn_metadata)
    compaction = metadata.get("compaction")
    return (
        metadata.get("request_kind") == "compaction"
        and isinstance(compaction, dict)
        and cast("dict[str, JsonValue]", compaction).get("phase") == "standalone_turn"
    )


class CodexAppServer:
    """Bounded JSON-RPC client for one local Codex app-server process."""

    _codex: Path
    _environment: dict[str, str]
    _next_id: int
    _notifications: list[dict[str, JsonValue]]
    _process: subprocess.Popen[str] | None

    def __init__(self, codex: Path, environment: dict[str, str]) -> None:
        self._codex = codex
        self._environment = environment
        self._next_id = 1
        self._notifications = []
        self._process = None

    def __enter__(self) -> Self:
        self._process = subprocess.Popen(  # noqa: S603
            (str(self._codex), "app-server"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._environment,
            text=True,
        )
        return self

    def __exit__(self, *_arguments: object) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            _ = self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            _ = self._process.wait(timeout=10)
        for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
            if stream is not None:
                stream.close()

    def call(self, method: str, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Send one JSON-RPC request and return its object result within ten seconds."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Codex app-server is not running")
        stdout = cast("TextIO", self._process.stdout)
        identifier = self._next_id
        self._next_id += 1
        payload = {"id": identifier, "jsonrpc": "2.0", "method": method, "params": params}
        _ = self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([stdout], [], [], remaining)[0]:
                raise TimeoutError("Codex app-server request timed out")
            line = stdout.readline()
            if not line:
                raise RuntimeError("Codex app-server closed before replying")
            response = _OBJECT_ADAPTER.validate_json(line)
            if response.get("id") != identifier:
                self._notifications.append(response)
                continue
            error = response.get("error")
            if isinstance(error, dict):
                raise RuntimeError(json.dumps(error, sort_keys=True))
            result = response.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Codex app-server result is not an object")
            return result

    def wait_for(self, method: str) -> dict[str, JsonValue]:
        """Wait at most ten seconds for one app-server notification method."""
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Codex app-server is not running")
        stdout = cast("TextIO", self._process.stdout)
        for index, notification in enumerate(self._notifications):
            if notification.get("method") == method:
                return self._notification_params(self._notifications.pop(index))
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([stdout], [], [], remaining)[0]:
                observed = tuple(notification.get("method") for notification in self._notifications)
                raise TimeoutError(f"Codex app-server did not emit {method}: {observed}")
            line = stdout.readline()
            if not line:
                raise RuntimeError("Codex app-server closed before notifying")
            notification = _OBJECT_ADAPTER.validate_json(line)
            if notification.get("method") == method:
                return self._notification_params(notification)
            self._notifications.append(notification)

    def wait_for_thread_settled(self, thread_id: str) -> None:
        """Poll the thread until it reaches an idle or terminal status within ten seconds."""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = self.call("thread/read", {"threadId": thread_id})
            thread = response.get("thread")
            if isinstance(thread, dict):
                status = thread.get("status")
                if isinstance(status, dict) and status.get("type") in {"idle", "systemError"}:
                    return
            time.sleep(0.05)
        raise TimeoutError(f"Codex app-server did not settle thread {thread_id}")

    def _notification_params(self, notification: dict[str, JsonValue]) -> dict[str, JsonValue]:
        params = notification.get("params")
        if isinstance(params, dict):
            return params
        raise RuntimeError("Codex app-server notification params are not an object")


class FakeCodexResponses:
    """Threaded deterministic provider accepting only loopback Responses calls."""

    requests: list[RecordedResponseRequest]
    rejected_targets: list[str]
    _server: ThreadingHTTPServer
    _thread: Thread

    def __init__(self) -> None:
        self.requests = []
        self.rejected_targets = []
        handler = self._handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def origin(self) -> str:
        """Return the loopback-only provider origin without an API path."""
        address = self._server.server_address
        return f"http://{address[0]}:{address[1]}"

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *_arguments: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        requests = self.requests
        rejected_targets = self.rejected_targets

        class ResponsesHandler(BaseHTTPRequestHandler):
            """Bound handler closing over the fixture's in-memory request log."""

            server_version: str = "FakeCodexResponses/1"
            sys_version: str = ""
            _requests: ClassVar[list[RecordedResponseRequest]] = requests
            _rejected_targets: ClassVar[list[str]] = rejected_targets

            def do_POST(self) -> None:
                if self.path != "/v1/responses":
                    self._rejected_targets.append(self.path)
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = _OBJECT_ADAPTER.validate_json(self.rfile.read(length))
                self._requests.append(RecordedResponseRequest(body, self.path))
                payload = json.dumps({"response": _RESPONSE, "type": "response.completed"})
                created = json.dumps(
                    {"response": {**_RESPONSE, "status": "in_progress"}, "type": "response.created"}
                )
                stream = (
                    f"event: response.created\ndata: {created}\n\n"
                    f"event: response.completed\ndata: {payload}\n\n"
                )
                encoded = stream.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                _ = self.wfile.write(encoded)

            @override
            def log_message(self, format: str, *_arguments: object) -> None:
                _ = format

        return ResponsesHandler
