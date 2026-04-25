from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from agentsofchaos_orchestrator.domain.enums import (
    NodeKind,
    NodeStatus,
    RuntimeCapability,
    RuntimeKind,
)
from agentsofchaos_orchestrator.domain.errors import RuntimeCancelledError
from agentsofchaos_orchestrator.domain.models import ContextSnapshot, Node
from agentsofchaos_orchestrator.infrastructure.runtime import (
    NoOpRuntimeAdapter,
    PiRuntimeAdapter,
    RuntimeCancellationToken,
    RuntimeEvent,
    RuntimeExecutionRequest,
)


class FakeProcessStdin:
    def __init__(self, process: FakePiProcess) -> None:
        self._process = process
        self._buffer = bytearray()
        self._closing = False

    def write(self, data: bytes) -> None:
        self._buffer.extend(data)
        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index == -1:
                break
            line = bytes(self._buffer[:newline_index])
            del self._buffer[: newline_index + 1]
            self._process.handle_command(json.loads(line.decode("utf-8")))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._closing = True

    def is_closing(self) -> bool:
        return self._closing

    async def wait_closed(self) -> None:
        return None


class FakePiProcess:
    def __init__(
        self,
        *,
        initial_session_file: str,
        child_session_file: str,
    ) -> None:
        self.stdin = FakeProcessStdin(self)
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.returncode: int | None = None
        self._exit_event = asyncio.Event()
        self._commands: list[dict[str, object]] = []
        self._session_file = initial_session_file
        self._child_session_file = child_session_file
        self._session_id = "session-initial"
        self._session_name: str | None = None
        self._assistant_text = "Implemented by pi."

    @property
    def commands(self) -> tuple[dict[str, object], ...]:
        return tuple(self._commands)

    def handle_command(self, command: dict[str, object]) -> None:
        self._commands.append(command)
        command_id = str(command["id"])
        command_type = str(command["type"])

        if command_type == "switch_session":
            self._session_file = str(command["sessionPath"])
            self._session_id = "session-source"
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "switch_session",
                    "success": True,
                    "data": {"cancelled": False},
                }
            )
            return

        if command_type == "clone":
            self._session_file = self._child_session_file
            self._session_id = "session-child"
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "clone",
                    "success": True,
                    "data": {"cancelled": False},
                }
            )
            return

        if command_type == "set_session_name":
            self._session_name = str(command["name"])
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "set_session_name",
                    "success": True,
                }
            )
            return

        if command_type == "get_state":
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "get_state",
                    "success": True,
                    "data": {
                        "sessionFile": self._session_file,
                        "sessionId": self._session_id,
                        "sessionName": self._session_name,
                        "model": {"provider": "openai", "id": "gpt-4o-mini"},
                    },
                }
            )
            return

        if command_type == "prompt":
            message = str(command["message"])
            assert "<aoc_context>" in message
            assert "Existing context." in message
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "prompt",
                    "success": True,
                }
            )
            assistant_message = {
                "role": "assistant",
                "content": [{"type": "text", "text": self._assistant_text}],
                "provider": "openai",
                "model": "gpt-4o-mini",
                "timestamp": 0,
            }
            self._emit_stdout({"type": "agent_start"})
            self._emit_stdout(
                {
                    "type": "message_update",
                    "message": assistant_message,
                    "assistantMessageEvent": {
                        "type": "text_delta",
                        "contentIndex": 0,
                        "delta": "Implemented by pi.",
                        "partial": assistant_message,
                    },
                }
            )
            self._emit_stdout({"type": "message_end", "message": assistant_message})
            self._emit_stdout({"type": "agent_end", "messages": [assistant_message]})
            return

        if command_type == "abort":
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "abort",
                    "success": True,
                }
            )
            return

        if command_type == "get_last_assistant_text":
            self._emit_stdout(
                {
                    "id": command_id,
                    "type": "response",
                    "command": "get_last_assistant_text",
                    "success": True,
                    "data": {"text": self._assistant_text},
                }
            )
            return

        if command_type == "extension_ui_response":
            return

        raise AssertionError(f"Unexpected command: {command}")

    def _emit_stdout(self, payload: dict[str, object]) -> None:
        line = json.dumps(payload).encode("utf-8") + b"\n"
        self.stdout.feed_data(line)

    def terminate(self) -> None:
        if self.returncode is not None:
            return
        self.returncode = 0
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self._exit_event.set()

    def kill(self) -> None:
        self.terminate()

    async def wait(self) -> int:
        await self._exit_event.wait()
        assert self.returncode is not None
        return self.returncode


def build_request(tmp_path: Path) -> RuntimeExecutionRequest:
    timestamp = datetime.now(timezone.utc)
    source_node = Node(
        id=uuid4(),
        project_id=uuid4(),
        kind=NodeKind.ROOT,
        parent_node_ids=(),
        code_snapshot_id=uuid4(),
        context_snapshot_id=uuid4(),
        status=NodeStatus.READY,
        title="Root",
        created_at=timestamp,
    )
    source_context = ContextSnapshot(
        id=uuid4(),
        project_id=source_node.project_id,
        summary="Existing context.",
        created_at=timestamp,
    )
    daemon_state_dir = tmp_path / ".aoc"
    return RuntimeExecutionRequest(
        run_id=uuid4(),
        planned_child_node_id=uuid4(),
        prompt="hello",
        source_node=source_node,
        source_context=source_context,
        worktree_path=tmp_path / "worktree",
        daemon_state_dir=daemon_state_dir,
    )


@pytest.mark.asyncio
async def test_noop_runtime_adapter_emits_normalized_events(tmp_path: Path) -> None:
    adapter = NoOpRuntimeAdapter()
    request = build_request(tmp_path)
    events: list[tuple[str, str | None]] = []

    async def capture(event: RuntimeEvent) -> None:
        events.append((event.kind, event.message))

    result = await adapter.execute(request=request, emit=capture)

    assert adapter.runtime_kind is RuntimeKind.CUSTOM
    assert RuntimeCapability.CANCELLATION in adapter.capabilities
    assert result.summary_text == "No-op prompt execution for: hello"
    assert events == [
        ("runtime.started", "No-op runtime started."),
        ("runtime.completed", "No-op runtime completed."),
    ]


@pytest.mark.asyncio
async def test_noop_runtime_adapter_honors_cancellation(tmp_path: Path) -> None:
    adapter = NoOpRuntimeAdapter()
    token = RuntimeCancellationToken()
    token.cancel()
    request = build_request(tmp_path)
    cancelled_request = RuntimeExecutionRequest(
        run_id=request.run_id,
        planned_child_node_id=request.planned_child_node_id,
        prompt=request.prompt,
        source_node=request.source_node,
        source_context=request.source_context,
        worktree_path=request.worktree_path,
        daemon_state_dir=request.daemon_state_dir,
        cancellation_token=token,
    )

    async def capture(_event: RuntimeEvent) -> None:
        return None

    with pytest.raises(RuntimeCancelledError):
        await adapter.execute(request=cancelled_request, emit=capture)


@pytest.mark.asyncio
async def test_pi_runtime_adapter_executes_over_rpc_and_updates_session_registry(
    tmp_path: Path,
) -> None:
    request = build_request(tmp_path)
    request.worktree_path.mkdir(parents=True, exist_ok=True)
    session_dir = request.daemon_state_dir / "pi-sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    source_session_path = session_dir / "source-session.jsonl"
    source_session_path.write_text('{"type":"session"}\n', encoding="utf-8")
    registry_path = session_dir / "node-session-map.json"
    registry_path.write_text(
        json.dumps({str(request.source_node.id): str(source_session_path)}),
        encoding="utf-8",
    )
    child_session_path = session_dir / "child-session.jsonl"
    fake_process = FakePiProcess(
        initial_session_file=str(session_dir / "initial-session.jsonl"),
        child_session_file=str(child_session_path),
    )
    events: list[RuntimeEvent] = []

    async def fake_process_factory(
        cwd: Path,
        argv: tuple[str, ...],
        env: dict[str, str],
    ) -> FakePiProcess:
        assert cwd == request.worktree_path
        assert argv[:4] == ("pi", "--mode", "rpc", "--session-dir")
        assert argv[4] == str(session_dir)
        assert env
        return fake_process

    async def capture(event: RuntimeEvent) -> None:
        events.append(event)

    adapter = PiRuntimeAdapter(process_factory=fake_process_factory)
    result = await adapter.execute(request=request, emit=capture)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    command_types = [str(command["type"]) for command in fake_process.commands]

    assert adapter.runtime_kind is RuntimeKind.PI
    assert RuntimeCapability.CANCELLATION in adapter.capabilities
    assert RuntimeCapability.SESSION_CLONE in adapter.capabilities
    assert result.summary_text == "Implemented by pi."
    assert result.metadata["sessionFile"] == str(child_session_path)
    assert result.metadata["sessionId"] == "session-child"
    assert registry[str(request.planned_child_node_id)] == str(child_session_path)
    assert command_types == [
        "switch_session",
        "clone",
        "set_session_name",
        "get_state",
        "prompt",
        "get_last_assistant_text",
        "get_state",
    ]
    assert result.transcript_text == "USER: hello\nASSISTANT: Implemented by pi.\n"
    assert any(event.kind == "runtime.session_cloned" for event in events)
    assert any(event.kind == "runtime.agent_start" for event in events)
    message_delta = next(event for event in events if event.kind == "runtime.message_delta")
    session_ready = next(event for event in events if event.kind == "runtime.session_ready")
    assert message_delta.durable is False
    assert session_ready.durable is True
    assert any(event.kind == "runtime.process_exited" for event in events)


def test_pi_runtime_adapter_identifies_itself_as_pi() -> None:
    adapter = PiRuntimeAdapter()
    assert adapter.runtime_kind is RuntimeKind.PI
    assert RuntimeCapability.RPC_STREAMING in adapter.capabilities
