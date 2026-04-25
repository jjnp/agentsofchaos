from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.runtime.base import RuntimeEvent, RuntimeEventSink
from agentsofchaos_orchestrator.infrastructure.runtime.pi.events import (
    JsonObject,
    normalize_pi_event,
    optional_object_dict,
    optional_object_list,
    optional_str,
)
from agentsofchaos_orchestrator.infrastructure.runtime.pi.jsonl import (
    iter_jsonl_lines,
    parse_json_object,
)
from agentsofchaos_orchestrator.infrastructure.runtime.pi.process import (
    AsyncProcess,
    PiProcessFactory,
    await_with_timeout,
)

_DIALOG_METHODS_REQUIRING_RESPONSE = {"select", "confirm", "input", "editor"}


class PiRpcClient:
    def __init__(
        self,
        *,
        cwd: Path,
        argv: tuple[str, ...],
        emit: RuntimeEventSink,
        command_timeout_seconds: float,
        shutdown_timeout_seconds: float,
        process_factory: PiProcessFactory,
        env: Mapping[str, str] | None,
    ) -> None:
        self._cwd = cwd
        self._argv = argv
        self._emit = emit
        self._command_timeout_seconds = command_timeout_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._process_factory = process_factory
        self._env = env
        self._process: AsyncProcess | None = None
        self._response_waiters: dict[str, asyncio.Future[JsonObject]] = {}
        self._stdout_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._wait_task: asyncio.Task[None] | None = None
        self._active_agent_future: asyncio.Future[JsonObject] | None = None
        self._generated_messages: list[JsonObject] = []

    @property
    def generated_messages(self) -> tuple[JsonObject, ...]:
        return tuple(self._generated_messages)

    async def emit(self, event: RuntimeEvent) -> None:
        await self._emit(event)

    async def start(self) -> None:
        env = dict(os.environ)
        if self._env is not None:
            env.update(self._env)
        process = await self._process_factory(self._cwd, self._argv, env)
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeExecutionError("Pi RPC subprocess did not expose all stdio pipes")
        self._process = process
        self._stdout_task = asyncio.create_task(self._consume_stdout(process.stdout))
        self._stderr_task = asyncio.create_task(self._consume_stderr(process.stderr))
        self._wait_task = asyncio.create_task(self._wait_for_exit(process))
        await self.emit(
            RuntimeEvent(
                kind="runtime.process_started",
                message="Started pi RPC subprocess.",
                payload={"argv": list(self._argv), "cwd": str(self._cwd)},
            )
        )

    def prepare_agent_run(self) -> None:
        self._active_agent_future = asyncio.get_running_loop().create_future()
        self._generated_messages = []

    async def expect_success(
        self,
        command: JsonObject,
        *,
        error_context: str,
    ) -> JsonObject:
        response = await self.send_command(command)
        if response.get("success") is True:
            return response
        error_message = optional_str(response.get("error")) or f"Failed while {error_context}"
        raise RuntimeExecutionError(error_message)

    async def send_command(self, command: JsonObject) -> JsonObject:
        command_id = optional_str(command.get("id")) or str(uuid4())
        command_type = optional_str(command.get("type")) or "unknown"
        if command_id in self._response_waiters:
            raise RuntimeExecutionError(f"Duplicate pi RPC command id: {command_id}")
        response_future: asyncio.Future[JsonObject] = asyncio.get_running_loop().create_future()
        self._response_waiters[command_id] = response_future
        try:
            await self.write_json_line({**command, "id": command_id})
            return await await_with_timeout(
                response_future,
                timeout_seconds=self._command_timeout_seconds,
                description=f"waiting for pi response to {command_type}",
            )
        finally:
            self._response_waiters.pop(command_id, None)

    async def write_json_line(self, payload: JsonObject) -> None:
        process = self._require_process()
        stdin = process.stdin
        if stdin is None:
            raise RuntimeExecutionError("Pi RPC stdin is unavailable")
        line = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            stdin.write(line)
            await stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as error:
            raise RuntimeExecutionError("Pi RPC subprocess stopped accepting input") from error

    async def abort(self) -> None:
        await self.expect_success({"type": "abort"}, error_context="aborting pi run")

    async def get_state(self) -> JsonObject:
        response = await self.expect_success(
            {"type": "get_state"},
            error_context="fetching pi state",
        )
        data = optional_object_dict(response.get("data"))
        if data is None:
            raise RuntimeExecutionError("Pi get_state response did not include a data object")
        return data

    async def get_last_assistant_text(self) -> str | None:
        response = await self.expect_success(
            {"type": "get_last_assistant_text"},
            error_context="fetching the last pi assistant message",
        )
        data = optional_object_dict(response.get("data"))
        return optional_str(data.get("text")) if data is not None else None

    async def wait_for_agent_completion(self) -> JsonObject:
        if self._active_agent_future is None:
            raise RuntimeExecutionError(
                "Pi agent completion was requested before a prompt was started"
            )
        return await self._active_agent_future

    async def close(self) -> None:
        process = self._process
        if process is not None:
            await self._close_process(process)
        await self._drain_task(self._stdout_task)
        await self._drain_task(self._stderr_task)
        await self._drain_task(self._wait_task)

    async def _close_process(self, process: AsyncProcess) -> None:
        stdin = process.stdin
        if stdin is not None and not stdin.is_closing():
            stdin.close()
            try:
                await await_with_timeout(
                    stdin.wait_closed(),
                    timeout_seconds=self._shutdown_timeout_seconds,
                    description="closing pi stdin",
                )
            except RuntimeExecutionError:
                pass

        if process.returncode is None:
            process.terminate()
            try:
                await await_with_timeout(
                    process.wait(),
                    timeout_seconds=self._shutdown_timeout_seconds,
                    description="waiting for pi to exit",
                )
            except RuntimeExecutionError:
                process.kill()
                await process.wait()

    async def _drain_task(self, task: asyncio.Task[None] | None) -> None:
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as error:
            with suppress(Exception):
                await self.emit(
                    RuntimeEvent(
                        kind="runtime.teardown_warning",
                        message=str(error),
                        payload={"error": str(error)},
                    )
                )

    async def _consume_stdout(self, reader: asyncio.StreamReader) -> None:
        try:
            async for line in iter_jsonl_lines(reader):
                payload = parse_json_object(line, source="pi stdout")
                await self._handle_stdout_payload(payload)
        except Exception as error:
            self._fail_pending(RuntimeExecutionError(str(error)))
            raise

    async def _consume_stderr(self, reader: asyncio.StreamReader) -> None:
        try:
            async for line in iter_jsonl_lines(reader):
                await self.emit(
                    RuntimeEvent(
                        kind="runtime.stderr",
                        message=line,
                        payload={"line": line},
                    )
                )
        except Exception as error:
            self._fail_pending(RuntimeExecutionError(str(error)))
            raise

    async def _wait_for_exit(self, process: AsyncProcess) -> None:
        exit_code = await process.wait()
        await self.emit(
            RuntimeEvent(
                kind="runtime.process_exited",
                message="Pi RPC subprocess exited.",
                payload={"exitCode": exit_code},
            )
        )
        if self._active_agent_future is not None and not self._active_agent_future.done():
            self._fail_pending(
                RuntimeExecutionError(
                    f"Pi RPC subprocess exited before prompt completion ({exit_code})"
                )
            )
            return
        if self._response_waiters:
            self._fail_pending(
                RuntimeExecutionError(
                    f"Pi RPC subprocess exited before command completion ({exit_code})"
                )
            )
            return
        if exit_code != 0:
            self._fail_pending(
                RuntimeExecutionError(f"Pi RPC subprocess exited with status {exit_code}")
            )

    async def _handle_stdout_payload(self, payload: JsonObject) -> None:
        payload_type = optional_str(payload.get("type"))
        if payload_type == "response":
            self._handle_response(payload)
            return
        if payload_type == "extension_ui_request":
            await self._handle_extension_ui_request(payload)
        self._capture_payload(payload)
        await self.emit(normalize_pi_event(payload))

    def _handle_response(self, payload: JsonObject) -> None:
        response_id = optional_str(payload.get("id"))
        if response_id is None:
            return
        waiter = self._response_waiters.get(response_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(payload)

    async def _handle_extension_ui_request(self, payload: JsonObject) -> None:
        method = optional_str(payload.get("method"))
        request_id = optional_str(payload.get("id"))
        if method not in _DIALOG_METHODS_REQUIRING_RESPONSE or request_id is None:
            return
        await self.write_json_line(
            {"type": "extension_ui_response", "id": request_id, "cancelled": True}
        )

    def _capture_payload(self, payload: JsonObject) -> None:
        payload_type = optional_str(payload.get("type"))
        if payload_type == "turn_end":
            message = optional_object_dict(payload.get("message"))
            tool_results = optional_object_list(payload.get("toolResults"))
            if message is not None:
                self._generated_messages.append(message)
            self._generated_messages.extend(tool_results)
            return
        if payload_type == "agent_end":
            self._generated_messages = list(optional_object_list(payload.get("messages")))
            if self._active_agent_future is not None and not self._active_agent_future.done():
                self._active_agent_future.set_result(payload)

    def _fail_pending(self, error: RuntimeExecutionError) -> None:
        for waiter in self._response_waiters.values():
            if not waiter.done():
                waiter.set_exception(error)
        if self._active_agent_future is not None and not self._active_agent_future.done():
            self._active_agent_future.set_exception(error)

    def _require_process(self) -> AsyncProcess:
        if self._process is None:
            raise RuntimeExecutionError("Pi RPC subprocess has not been started")
        return self._process
