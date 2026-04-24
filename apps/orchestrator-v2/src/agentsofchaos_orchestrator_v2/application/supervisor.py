from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from agentsofchaos_orchestrator_v2.domain.errors import RuntimeCancelledError
from agentsofchaos_orchestrator_v2.infrastructure.runtime import RuntimeCancellationToken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActiveRun:
    run_id: UUID
    cancellation_token: RuntimeCancellationToken
    task: asyncio.Task[object]


class RunSupervisor:
    def __init__(self) -> None:
        self._active_runs: dict[UUID, ActiveRun] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        run_id: UUID,
        cancellation_token: RuntimeCancellationToken,
        awaitable_factory: Callable[[], Awaitable[object]],
    ) -> None:
        async with self._lock:
            existing = self._active_runs.get(run_id)
            if existing is not None and not existing.task.done():
                raise RuntimeError(f"Run is already active: {run_id}")
            task = asyncio.create_task(awaitable_factory())
            active_run = ActiveRun(
                run_id=run_id,
                cancellation_token=cancellation_token,
                task=task,
            )
            self._active_runs[run_id] = active_run
        task.add_done_callback(lambda _task: asyncio.create_task(self._forget(run_id)))

    async def cancel(self, run_id: UUID) -> bool:
        async with self._lock:
            active_run = self._active_runs.get(run_id)
        if active_run is None:
            return False
        active_run.cancellation_token.cancel()
        return True

    async def is_active(self, run_id: UUID) -> bool:
        async with self._lock:
            active_run = self._active_runs.get(run_id)
        return active_run is not None and not active_run.task.done()

    async def shutdown(self) -> None:
        async with self._lock:
            active_runs = tuple(self._active_runs.values())
            self._active_runs.clear()
        for active_run in active_runs:
            active_run.cancellation_token.cancel()
            active_run.task.cancel()
        for active_run in active_runs:
            try:
                await active_run.task
            except (asyncio.CancelledError, RuntimeCancelledError):
                pass
            except Exception:
                logger.exception(
                    "Active run failed during supervisor shutdown",
                    extra={"run_id": str(active_run.run_id)},
                )

    async def _forget(self, run_id: UUID) -> None:
        async with self._lock:
            active_run = self._active_runs.get(run_id)
            if active_run is None or not active_run.task.done():
                return
            self._active_runs.pop(run_id, None)
            try:
                active_run.task.result()
            except (asyncio.CancelledError, RuntimeCancelledError):
                pass
            except Exception:
                logger.exception("Background run task failed", extra={"run_id": str(run_id)})
