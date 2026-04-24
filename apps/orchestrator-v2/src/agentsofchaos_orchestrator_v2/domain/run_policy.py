from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agentsofchaos_orchestrator_v2.domain.enums import RunStatus
from agentsofchaos_orchestrator_v2.domain.errors import OrchestratorError
from agentsofchaos_orchestrator_v2.domain.models import Run


class InvalidRunTransitionError(OrchestratorError):
    """Raised when run lifecycle code attempts an invalid status transition."""


_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class RunLifecyclePolicy:
    def start(self, run: Run, *, started_at: datetime) -> Run:
        self._ensure_transition(run.status, RunStatus.RUNNING)
        return run.model_copy(update={"status": RunStatus.RUNNING, "started_at": started_at})

    def succeed(self, run: Run, *, transcript_path: str, finished_at: datetime) -> Run:
        self._ensure_transition(run.status, RunStatus.SUCCEEDED)
        return run.model_copy(
            update={
                "status": RunStatus.SUCCEEDED,
                "transcript_path": transcript_path,
                "finished_at": finished_at,
            }
        )

    def fail(self, run: Run, *, error_message: str, finished_at: datetime) -> Run:
        self._ensure_transition(run.status, RunStatus.FAILED)
        return run.model_copy(
            update={
                "status": RunStatus.FAILED,
                "error_message": error_message,
                "finished_at": finished_at,
            }
        )

    def cancel(
        self,
        run: Run,
        *,
        finished_at: datetime,
        transcript_path: str | None = None,
    ) -> Run:
        self._ensure_transition(run.status, RunStatus.CANCELLED)
        updates: dict[str, object] = {
            "status": RunStatus.CANCELLED,
            "finished_at": finished_at,
        }
        if transcript_path is not None:
            updates["transcript_path"] = transcript_path
        return run.model_copy(update=updates)

    def _ensure_transition(self, source: RunStatus, target: RunStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS[source]:
            raise InvalidRunTransitionError(
                f"Invalid run transition: {source.value} -> {target.value}"
            )
