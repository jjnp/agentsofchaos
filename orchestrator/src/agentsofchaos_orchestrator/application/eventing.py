from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.outbox import OutboxDispatcher
from agentsofchaos_orchestrator.domain.enums import EventTopic, RuntimeKind
from agentsofchaos_orchestrator.domain.models import EventRecord
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.runtime import RuntimeEvent
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


class ApplicationEventRecorder:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: InMemoryEventBus,
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._outbox = OutboxDispatcher(
            session_factory=session_factory,
            event_bus=event_bus,
            now=now,
        )
        self._now = now
        self._new_uuid = new_uuid

    async def record_and_publish(
        self,
        *,
        project_id: UUID,
        topic: EventTopic,
        payload: dict[str, object],
        created_at: datetime,
    ) -> EventRecord:
        event = await self.record_event(
            project_id=project_id,
            topic=topic,
            payload=payload,
            created_at=created_at,
        )
        await self._outbox.dispatch_event(event.id)
        return event

    async def record_event(
        self,
        *,
        project_id: UUID,
        topic: EventTopic,
        payload: dict[str, object],
        created_at: datetime,
    ) -> EventRecord:
        async with self._unit_of_work() as unit_of_work:
            event = await unit_of_work.events.add(
                project_id=project_id,
                topic=topic,
                payload=payload,
                created_at=created_at,
            )
            await unit_of_work.outbox.add_from_event(event)
            await unit_of_work.commit()
            return event

    async def emit_runtime_event(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        runtime_kind: RuntimeKind,
        event: RuntimeEvent,
    ) -> None:
        created_at = self._now()
        payload = {
            "project_id": str(project_id),
            "run_id": str(run_id),
            "runtime_kind": runtime_kind.value,
            "runtime_event": event.model_dump(mode="json"),
        }
        if not event.durable:
            await self._outbox.publish_live(
                EventRecord(
                    id=self._new_uuid(),
                    project_id=project_id,
                    topic=EventTopic.RUNTIME_EVENT,
                    payload=payload,
                    created_at=created_at,
                )
            )
            return

        await self.record_and_publish(
            project_id=project_id,
            topic=EventTopic.RUNTIME_EVENT,
            payload=payload,
            created_at=created_at,
        )

    async def dispatch_pending(self, *, limit: int = 100) -> int:
        return await self._outbox.dispatch_pending(limit=limit)
