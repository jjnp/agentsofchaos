from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentsofchaos_orchestrator.domain.enums import RuntimeCapability, RuntimeKind
from agentsofchaos_orchestrator.domain.errors import RuntimeCancelledError
from agentsofchaos_orchestrator.domain.models import ContextSnapshot, Node


class RuntimeModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuntimeEvent(RuntimeModel):
    kind: str = Field(min_length=1)
    message: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    durable: bool = True


class RuntimeExecutionResult(RuntimeModel):
    transcript_text: str
    summary_text: str
    metadata: dict[str, object] = Field(default_factory=dict)


class RuntimeCancellationToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def throw_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise RuntimeCancelledError("Runtime execution was cancelled")


@dataclass(frozen=True)
class RuntimeExecutionRequest:
    run_id: UUID
    planned_child_node_id: UUID
    prompt: str
    source_node: Node
    source_context: ContextSnapshot
    worktree_path: Path
    daemon_state_dir: Path
    cancellation_token: RuntimeCancellationToken = field(
        default_factory=RuntimeCancellationToken
    )


RuntimeEventSink = Callable[[RuntimeEvent], Awaitable[None]]


class RuntimeAdapter(Protocol):
    @property
    def runtime_kind(self) -> RuntimeKind:
        ...

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        ...

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        ...
