from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from agentsofchaos_orchestrator.domain.enums import RuntimeCapability, RuntimeKind
from agentsofchaos_orchestrator.domain.errors import RuntimeCancelledError, RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.runtime.base import (
    RuntimeCancellationToken,
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator.infrastructure.runtime.pi.context import build_contextual_prompt
from agentsofchaos_orchestrator.infrastructure.runtime.pi.events import optional_object_dict
from agentsofchaos_orchestrator.infrastructure.runtime.pi.process import await_with_timeout
from agentsofchaos_orchestrator.infrastructure.runtime.pi.rpc_client import PiRpcClient
from agentsofchaos_orchestrator.infrastructure.runtime.pi.session_registry import (
    load_node_session_path,
    store_node_session_path,
)
from agentsofchaos_orchestrator.infrastructure.runtime.pi.transcript import build_transcript
from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    SandboxBackend,
    SandboxNetworkPolicy,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.none_backend import NoSandboxBackend

# Default env names the Pi adapter pulls from os.environ. Anything else
# stays inside the daemon — the sandbox layer relies on this whitelist
# to keep credentials and host-specific paths out of the agent process.
_DEFAULT_PI_ENV_WHITELIST: tuple[str, ...] = (
    "HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "TERM",
    "USER",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_BASE_URL",
    "PI_AUTH_TOKEN",
    "PI_HOME",
)


@dataclass(frozen=True)
class PiRuntimeAdapter:
    pi_binary: str = "pi"
    model: str | None = None
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    session_dir_name: str = "pi-sessions"
    command_timeout_seconds: float = 30.0
    run_timeout_seconds: float | None = None
    shutdown_timeout_seconds: float = 5.0
    sandbox: SandboxBackend = field(default_factory=NoSandboxBackend)
    env_whitelist: tuple[str, ...] = _DEFAULT_PI_ENV_WHITELIST
    extra_env: Mapping[str, str] | None = None
    network: SandboxNetworkPolicy = SandboxNetworkPolicy.FULL
    extra_read_only_mounts: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if not self.pi_binary.strip():
            raise ValueError("pi_binary must not be empty")
        if not self.session_dir_name.strip():
            raise ValueError("session_dir_name must not be empty")
        if self.command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be greater than zero")
        if self.run_timeout_seconds is not None and self.run_timeout_seconds <= 0:
            raise ValueError("run_timeout_seconds must be greater than zero when set")
        if self.shutdown_timeout_seconds <= 0:
            raise ValueError("shutdown_timeout_seconds must be greater than zero")

    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.PI

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset(
            {
                RuntimeCapability.RPC_STREAMING,
                RuntimeCapability.CANCELLATION,
                RuntimeCapability.SESSION_PERSISTENCE,
                RuntimeCapability.SESSION_CLONE,
                RuntimeCapability.STEERING,
                RuntimeCapability.FOLLOW_UP,
                RuntimeCapability.CUSTOM_TOOLS,
                RuntimeCapability.IMAGE_INPUT,
                RuntimeCapability.MODEL_SWITCHING,
            }
        )

    async def probe(self) -> None:
        """Verify pi can run on this host.

        Three checks, in order — first failure raises. Diagnostic
        messages are intentionally specific so an operator hitting
        `/health/runtime` can tell what's wrong without grepping logs.
        """
        import shutil

        # 1. Binary on PATH (or absolute path that exists).
        if Path(self.pi_binary).is_absolute():
            if not Path(self.pi_binary).is_file():
                raise RuntimeExecutionError(
                    f"pi binary not found at configured path: {self.pi_binary}"
                )
        else:
            if shutil.which(self.pi_binary) is None:
                raise RuntimeExecutionError(
                    f"pi binary {self.pi_binary!r} is not on PATH; install pi-mono "
                    "or set AOC_PI_BINARY to the correct path"
                )
        # 2. Config dir present (auth.json + settings.json) — without
        # these pi can't authenticate to its provider.
        config_dir = Path.home() / ".pi" / "agent"
        missing: list[str] = []
        if not (config_dir / "auth.json").is_file():
            missing.append("auth.json")
        if not (config_dir / "settings.json").is_file():
            missing.append("settings.json")
        if missing:
            raise RuntimeExecutionError(
                f"pi config missing in {config_dir}: {', '.join(missing)}. "
                "Run `pi auth login` and configure a default model first."
            )

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        request.cancellation_token.throw_if_cancelled()
        session_dir = request.daemon_state_dir / self.session_dir_name
        session_dir.mkdir(parents=True, exist_ok=True)
        session_registry_path = session_dir / "node-session-map.json"
        source_session_file = await load_node_session_path(
            session_registry_path,
            node_id=request.source_node.id,
        )
        source_session_path = self._resolve_source_session_path(source_session_file)
        client = PiRpcClient(
            cwd=request.worktree_path,
            argv=self._build_argv(session_dir),
            emit=emit,
            command_timeout_seconds=self.command_timeout_seconds,
            shutdown_timeout_seconds=self.shutdown_timeout_seconds,
            sandbox=self.sandbox,
            env=self._build_env(),
            # Pi reads its config and credentials from ~/.pi/agent (and
            # any extra paths the operator wired in). Without these RO
            # mounts the agent inside a real sandbox can't find
            # auth.json or settings.json.
            read_only_mounts=self._build_read_only_mounts(),
            # Pi writes its session JSONL files to the session dir,
            # which lives under the daemon state — outside the worktree
            # — so it has to be RW-mounted explicitly. Otherwise the
            # writes either fail or land on the sandbox's tmpfs and
            # are lost the moment the namespace exits.
            read_write_mounts=(session_dir,),
            cancellation_token=request.cancellation_token,
            network=self.network,
        )
        session_name = _session_name(request)
        session_file: str | None = None
        session_id: str | None = None
        model: object | None = None
        context_injected = False

        await client.start()
        try:
            request.cancellation_token.throw_if_cancelled()
            if source_session_file is not None and source_session_path is None:
                await _emit_missing_source_session(emit, source_session_file)
            if source_session_path is not None:
                await self._continue_from_source_session(
                    client=client,
                    source_session_path=source_session_path,
                    source_node_id=request.source_node.id,
                    new_worktree=request.worktree_path,
                )

            await client.expect_success(
                {"type": "set_session_name", "name": session_name},
                error_context="setting pi session name",
            )
            state = await client.get_state()
            session_file = _optional_state_str(state, "sessionFile")
            session_id = _optional_state_str(state, "sessionId")
            model = state.get("model")
            if session_file is not None:
                await store_node_session_path(
                    session_registry_path,
                    node_id=request.planned_child_node_id,
                    session_file=session_file,
                )

            await emit(
                RuntimeEvent(
                    kind="runtime.session_ready",
                    message="Pi session is ready for execution.",
                    payload={
                        "sessionFile": session_file,
                        "sessionId": session_id,
                        "sessionName": session_name,
                    },
                )
            )

            request.cancellation_token.throw_if_cancelled()
            contextual_prompt = build_contextual_prompt(
                prompt=request.prompt,
                source_context=request.source_context,
            )
            context_injected = contextual_prompt.injected
            client.prepare_agent_run()
            await client.expect_success(
                {"type": "prompt", "message": contextual_prompt.prompt},
                error_context="sending prompt to pi",
            )
            await emit(
                RuntimeEvent(
                    kind="runtime.prompt_accepted",
                    message="Pi accepted the prompt.",
                    payload={
                        "prompt": request.prompt,
                        "contextInjected": contextual_prompt.injected,
                    },
                )
            )
            await await_with_timeout(
                _wait_for_completion_or_cancel(
                    client=client,
                    cancellation_token=request.cancellation_token,
                    emit=emit,
                ),
                timeout_seconds=self.run_timeout_seconds,
                description="waiting for pi to finish the prompt",
            )

            last_assistant_text = await client.get_last_assistant_text()
            final_state = await client.get_state()
            final_session_file = _optional_state_str(final_state, "sessionFile") or session_file
            final_session_id = _optional_state_str(final_state, "sessionId") or session_id
            if final_session_file is not None:
                await store_node_session_path(
                    session_registry_path,
                    node_id=request.planned_child_node_id,
                    session_file=final_session_file,
                )

            return RuntimeExecutionResult(
                transcript_text=build_transcript(
                    prompt=request.prompt,
                    messages=client.generated_messages,
                ),
                summary_text=_summary_text(
                    assistant_text=last_assistant_text,
                    prompt=request.prompt,
                ),
                metadata={
                    "piBinary": self.pi_binary,
                    "model": model if isinstance(model, dict) else final_state.get("model"),
                    "sessionFile": final_session_file,
                    "sessionId": final_session_id,
                    "sessionName": session_name,
                    "sourceSessionFile": source_session_file,
                    "contextInjected": contextual_prompt.injected,
                },
            )
        except RuntimeCancelledError as error:
            final_state = await _safe_get_state(client)
            final_session_file = _optional_state_str(final_state, "sessionFile") or session_file
            final_session_id = _optional_state_str(final_state, "sessionId") or session_id
            if final_session_file is not None:
                await store_node_session_path(
                    session_registry_path,
                    node_id=request.planned_child_node_id,
                    session_file=final_session_file,
                )
            raise RuntimeCancelledError(
                str(error),
                transcript_text=build_transcript(
                    prompt=request.prompt,
                    messages=client.generated_messages,
                ),
                runtime_metadata={
                    "piBinary": self.pi_binary,
                    "model": model if isinstance(model, dict) else final_state.get("model"),
                    "sessionFile": final_session_file,
                    "sessionId": final_session_id,
                    "sessionName": session_name,
                    "sourceSessionFile": source_session_file,
                    "contextInjected": context_injected,
                    "cancelled": True,
                },
            ) from error
        finally:
            await client.close()

    def _build_argv(self, session_dir: Path) -> tuple[str, ...]:
        argv: list[str] = [self.pi_binary, "--mode", "rpc", "--session-dir", str(session_dir)]
        if self.model is not None:
            argv.extend(["--model", self.model])
        argv.extend(self.extra_args)
        return tuple(argv)

    def _build_env(self) -> dict[str, str]:
        """Resolve the env the agent process will see.

        Pulls only whitelisted vars out of the daemon's environment so
        the sandbox boundary stays meaningful, then layers explicit
        overrides on top.
        """
        env: dict[str, str] = {}
        for name in self.env_whitelist:
            value = os.environ.get(name)
            if value is not None:
                env[name] = value
        if self.extra_env is not None:
            env.update(self.extra_env)
        return env

    def _build_read_only_mounts(self) -> tuple[Path, ...]:
        """Read-only mounts pi expects to find inside the sandbox.

        Pi reads ``~/.pi/agent/`` for ``auth.json`` and
        ``settings.json``. We always include it (when it exists on the
        host) so an operator who points the daemon at the bubblewrap or
        docker backend doesn't have to remember to wire creds in by
        hand. Anything explicitly listed in ``extra_read_only_mounts``
        layers on top.
        """
        mounts: list[Path] = []
        default_pi_config = Path.home() / ".pi" / "agent"
        if default_pi_config.exists():
            mounts.append(default_pi_config)
        mounts.extend(self.extra_read_only_mounts)
        return tuple(mounts)

    def _resolve_source_session_path(self, session_file: str | None) -> Path | None:
        if session_file is None:
            return None
        session_path = Path(session_file)
        return session_path if session_path.is_file() else None

    async def _continue_from_source_session(
        self,
        *,
        client: PiRpcClient,
        source_session_path: Path,
        source_node_id: UUID,
        new_worktree: Path,
    ) -> bool:
        """Fork the parent's pi session into the new run.

        Each prompt run executes in a fresh worktree; the parent
        worktree is cleaned up at end-of-run. Pi's `switch_session`
        sanity-checks the cwd recorded in the session JSONL and
        refuses if that path no longer exists. We rewrite the session
        file's stored cwd to point at the *current* run's worktree
        before calling switch_session — pi sees a valid cwd, the
        switch succeeds, and clone proceeds normally so the new run
        inherits the parent's tool history.

        The fallback (catching the cwd-rejection error) stays as a
        defensive layer for unexpected rejections, but in the common
        path the rewrite makes it unreachable.
        """
        rewritten = _rewrite_session_cwd(source_session_path, new_worktree)
        if rewritten is not None:
            await client.emit(
                RuntimeEvent(
                    kind="runtime.session_cwd_rewritten",
                    message=(
                        "Source pi session cwd rewrote to current worktree so "
                        "switch_session sees a valid path."
                    ),
                    payload={
                        "source_node_id": str(source_node_id),
                        "source_session_file": str(source_session_path),
                        "previous_cwd": rewritten,
                        "new_cwd": str(new_worktree),
                    },
                )
            )

        try:
            _expect_not_cancelled(
                await client.expect_success(
                    {"type": "switch_session", "sessionPath": str(source_session_path)},
                    error_context="switching to source pi session",
                ),
                action="Pi source session switch",
            )
        except RuntimeExecutionError as exc:
            if "working directory does not exist" not in str(exc):
                raise
            # Defensive: rewrite should make this unreachable, but keep
            # the fallback so unexpected pi behaviour doesn't kill runs.
            await client.emit(
                RuntimeEvent(
                    kind="runtime.session_clone_skipped",
                    message=(
                        "Source pi session points at a worktree that no longer exists; "
                        "starting a fresh session instead."
                    ),
                    payload={
                        "source_node_id": str(source_node_id),
                        "source_session_file": str(source_session_path),
                        "reason": str(exc),
                    },
                )
            )
            return False
        _expect_not_cancelled(
            await client.expect_success(
                {"type": "clone"},
                error_context="cloning source pi session",
            ),
            action="Pi source session clone",
        )
        await client.emit(
            RuntimeEvent(
                kind="runtime.session_cloned",
                message="Pi session cloned from source node session.",
                payload={
                    "source_node_id": str(source_node_id),
                    "source_session_file": str(source_session_path),
                },
            )
        )
        return True


def _rewrite_session_cwd(session_path: Path, new_cwd: Path) -> str | None:
    """Rewrite the `cwd` field on a pi session JSONL's first line if
    its current value doesn't exist on disk.

    Pi's session JSONL has a `{"type":"session", "cwd": "...", ...}` as
    line 0. Pi appends events; it never rewrites that header during a
    session, so editing it from the outside is safe between runs. We
    return the previous value as a string (for telemetry) when we
    rewrote, or `None` when no rewrite was needed (cwd already valid,
    file missing, or unparseable header).
    """
    try:
        with session_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return None
    if not lines:
        return None
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(header, dict) or header.get("type") != "session":
        return None
    stored_cwd = header.get("cwd")
    if not isinstance(stored_cwd, str):
        return None
    if Path(stored_cwd).is_dir():
        return None
    header["cwd"] = str(new_cwd)
    lines[0] = json.dumps(header) + "\n"
    try:
        session_path.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return None
    return stored_cwd


async def _wait_for_completion_or_cancel(
    *,
    client: PiRpcClient,
    cancellation_token: RuntimeCancellationToken,
    emit: RuntimeEventSink,
) -> None:
    completion_task = asyncio.create_task(client.wait_for_agent_completion())
    cancellation_task = asyncio.create_task(cancellation_token.wait())
    try:
        done, _pending = await asyncio.wait(
            {completion_task, cancellation_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancellation_task in done:
            await emit(
                RuntimeEvent(
                    kind="runtime.cancel_requested",
                    message="Runtime cancellation was requested.",
                    payload={},
                )
            )
            with suppress(RuntimeExecutionError):
                await client.abort()
            raise RuntimeCancelledError("Pi runtime execution was cancelled")
        await completion_task
    finally:
        for task in (completion_task, cancellation_task):
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


async def _emit_missing_source_session(emit: RuntimeEventSink, session_file: str) -> None:
    await emit(
        RuntimeEvent(
            kind="runtime.session_missing",
            message="Source pi session file was not found; using a fresh session.",
            payload={"sourceSessionFile": session_file},
        )
    )


def _session_name(request: RuntimeExecutionRequest) -> str:
    return f"aoc:{request.source_node.id}:{request.planned_child_node_id}:{request.run_id}"


async def _safe_get_state(client: PiRpcClient) -> dict[str, object]:
    with suppress(RuntimeExecutionError, asyncio.TimeoutError):
        return await client.get_state()
    return {}


def _optional_state_str(state: dict[str, object], key: str) -> str | None:
    value = state.get(key)
    return value if isinstance(value, str) else None


def _summary_text(*, assistant_text: str | None, prompt: str) -> str:
    if assistant_text is not None and assistant_text.strip():
        return assistant_text.strip()
    return f"Pi prompt execution for: {prompt}"


def _expect_not_cancelled(response: dict[str, object], *, action: str) -> None:
    data = optional_object_dict(response.get("data"))
    cancelled = bool(data.get("cancelled")) if data is not None else False
    if cancelled:
        raise RuntimeExecutionError(f"{action} was cancelled by an extension")
