from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator_v2.domain.models import EventRecord
from agentsofchaos_orchestrator_v2.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator_v2.infrastructure.unit_of_work import UnitOfWorkFactory


class OutboxDispatcher:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: InMemoryEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._event_bus = event_bus
        self._now = now

    async def publish_live(self, event: EventRecord) -> None:
        await self._event_bus.publish(event)

    async def dispatch_pending(self, *, limit: int = 100) -> int:
        async with self._unit_of_work() as unit_of_work:
            events = await unit_of_work.outbox.list_unpublished(limit=limit)

        published_count = 0
        for event in events:
            await self.dispatch_event(event.id)
            published_count += 1
        return published_count

    async def dispatch_event(self, event_id: UUID) -> None:
        event = await self._load_event(event_id)
        if event is None:
            return
        # Claim before publishing: only the winning call publishes to the bus.
        # This prevents a race between the inline record_and_publish path and
        # the background OutboxDispatchWorker both delivering the same event.
        claimed = await self.mark_published(event.id)
        if not claimed:
            return
        await self._event_bus.publish(event)

    async def mark_published(self, event_id: UUID) -> bool:
        async with self._unit_of_work() as unit_of_work:
            claimed = await unit_of_work.outbox.mark_published(
                event_id, published_at=self._now()
            )
            await unit_of_work.commit()
            return claimed

    async def _load_event(self, event_id: UUID) -> EventRecord | None:
        async with self._unit_of_work() as unit_of_work:
            return await unit_of_work.outbox.get_unpublished_event(event_id)
