from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentsofchaos_orchestrator.domain.enums import (
    ContextResolutionChoice,
    ContextSection,
    RuntimeCapability,
    RuntimeKind,
)
from agentsofchaos_orchestrator.domain.errors import RuntimeCancelledError
from agentsofchaos_orchestrator.domain.models import ContextSnapshot, Node


class RuntimeModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuntimeEvent(RuntimeModel):
    kind: str = Field(min_length=1)
    message: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    durable: bool = True


class ContextItemEdit(RuntimeModel):
    """Mutation a runtime asks the projection to apply to the child snapshot.

    If `item_id` matches an existing item in `section`, that item's text is
    replaced. Otherwise, a new item with that id is appended. This is the
    only mechanism by which a runtime can target an inherited context item
    — without it, projections only ever add fresh items, so divergent edits
    never collide and merges never see context conflicts.
    """

    section: ContextSection
    item_id: UUID
    text: str = Field(min_length=1)


class ContextResolutionDecision(RuntimeModel):
    """How a resolution-run chose to resolve a single context conflict."""

    section: ContextSection
    item_id: UUID
    chosen: ContextResolutionChoice
    text: str = Field(min_length=1)
    rationale: str = ""


class RuntimeExecutionResult(RuntimeModel):
    transcript_text: str
    summary_text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    context_edits: tuple[ContextItemEdit, ...] = ()
    context_resolutions: tuple[ContextResolutionDecision, ...] = ()


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

    async def probe(self) -> None:
        """Verify the adapter can run on this host.

        Implementations check that any host-side prerequisites are
        satisfied (binary on PATH, credentials present, runtime daemon
        reachable, etc.) and raise `RuntimeExecutionError` with a
        human-readable message when they aren't. Distinct from
        `SandboxBackend.probe` which gates the spawn boundary; this
        gates the runtime itself. Cheap operation — called from the
        `/health/runtime` route on every request, not just startup.
        """
        ...

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        ...
