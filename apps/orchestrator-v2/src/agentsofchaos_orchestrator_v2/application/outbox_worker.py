from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from agentsofchaos_orchestrator_v2.application.eventing import ApplicationEventRecorder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboxWorkerConfig:
    poll_interval_seconds: float = 0.5
    batch_size: int = 100


class OutboxDispatchWorker:
    def __init__(
        self,
        *,
        events: ApplicationEventRecorder,
        config: OutboxWorkerConfig | None = None,
    ) -> None:
        self._events = events
        self._config = config or OutboxWorkerConfig()
        self._task: asyncio.Task[None] | None = None
        self._stop_requested = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_requested.clear()
        self._task = asyncio.create_task(self._run(), name="aoc-outbox-dispatcher")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop_requested.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while not self._stop_requested.is_set():
            try:
                await self._events.dispatch_pending(limit=self._config.batch_size)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox dispatcher iteration failed")
            try:
                await asyncio.wait_for(
                    self._stop_requested.wait(),
                    timeout=self._config.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
