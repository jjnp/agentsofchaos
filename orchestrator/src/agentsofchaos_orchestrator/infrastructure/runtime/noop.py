from __future__ import annotations

from agentsofchaos_orchestrator.domain.enums import RuntimeCapability, RuntimeKind
from agentsofchaos_orchestrator.infrastructure.runtime.base import (
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)


class NoOpRuntimeAdapter:
    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.NOOP

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        request.cancellation_token.throw_if_cancelled()
        await emit(
            RuntimeEvent(
                kind="runtime.started",
                message="No-op runtime started.",
                payload={"worktree_path": str(request.worktree_path)},
            )
        )
        await emit(
            RuntimeEvent(
                kind="runtime.completed",
                message="No-op runtime completed.",
                payload={},
            )
        )
        request.cancellation_token.throw_if_cancelled()
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: No-op runtime executed.\n",
            summary_text=f"No-op prompt execution for: {request.prompt}",
        )
