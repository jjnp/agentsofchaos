from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from agentsofchaos_orchestrator.domain.models import EventRecord


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[EventRecord]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, event: EventRecord) -> None:
        async with self._lock:
            subscribers = tuple(self._subscribers.get(event.project_id, set()))

        for queue in subscribers:
            await queue.put(event)

    @asynccontextmanager
    async def subscribe(self, project_id: UUID) -> AsyncIterator[asyncio.Queue[EventRecord]]:
        queue: asyncio.Queue[EventRecord] = asyncio.Queue()
        async with self._lock:
            self._subscribers[project_id].add(queue)

        try:
            yield queue
        finally:
            async with self._lock:
                project_subscribers = self._subscribers.get(project_id)
                if project_subscribers is None:
                    return
                project_subscribers.discard(queue)
                if not project_subscribers:
                    self._subscribers.pop(project_id, None)
