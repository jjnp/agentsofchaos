from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.domain.enums import ArtifactKind, EventTopic
from agentsofchaos_orchestrator.domain.models import Artifact, EventRecord
from agentsofchaos_orchestrator.application.outbox import OutboxDispatcher
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.repositories import EventRepository
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class ArtifactInput:
    kind: ArtifactKind
    path: str
    media_type: str
    sha256: str
    size_bytes: int
    artifact_metadata: dict[str, object]


class ArtifactRecorder:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: InMemoryEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._outbox = OutboxDispatcher(
            session_factory=session_factory,
            event_bus=event_bus,
            now=now,
        )

    async def record_artifact(
        self,
        *,
        project_id: UUID,
        kind: ArtifactKind,
        path: Path,
        media_type: str,
        artifact_metadata: dict[str, object],
        created_at: datetime,
        run_id: UUID | None = None,
        node_id: UUID | None = None,
    ) -> Artifact | None:
        artifact_input = await self._artifact_input(
            kind=kind,
            path=path,
            media_type=media_type,
            metadata=artifact_metadata,
        )
        if artifact_input is None:
            return None
        artifacts, events = await self._persist_artifacts(
            project_id=project_id,
            run_id=run_id,
            node_id=node_id,
            artifact_inputs=(artifact_input,),
            created_at=created_at,
        )
        for event in events:
            await self._outbox.dispatch_event(event.id)
        return artifacts[0] if artifacts else None

    async def record_run_artifacts(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        node_id: UUID | None,
        transcript_path: Path,
        runtime_metadata: dict[str, object],
        created_at: datetime,
    ) -> tuple[Artifact, ...]:
        artifact_inputs = [
            await self._artifact_input(
                kind=ArtifactKind.RUNTIME_TRANSCRIPT,
                path=transcript_path,
                media_type="text/plain; charset=utf-8",
                metadata={"source": "runtime_result.transcript_text"},
            )
        ]
        session_file = runtime_metadata.get("sessionFile")
        if isinstance(session_file, str):
            artifact_inputs.append(
                await self._artifact_input(
                    kind=ArtifactKind.RUNTIME_SESSION,
                    path=Path(session_file),
                    media_type="application/jsonl",
                    metadata={"runtime": "pi"},
                )
            )

        artifacts, events = await self._persist_artifacts(
            project_id=project_id,
            run_id=run_id,
            node_id=node_id,
            artifact_inputs=tuple(input for input in artifact_inputs if input is not None),
            created_at=created_at,
        )
        for event in events:
            await self._outbox.dispatch_event(event.id)
        return artifacts

    async def _persist_artifacts(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        node_id: UUID | None,
        artifact_inputs: tuple[ArtifactInput, ...],
        created_at: datetime,
    ) -> tuple[tuple[Artifact, ...], tuple[EventRecord, ...]]:
        async with self._unit_of_work() as unit_of_work:
            persisted_artifacts: list[Artifact] = []
            persisted_events: list[EventRecord] = []
            for artifact_input in artifact_inputs:
                artifact = await unit_of_work.artifacts.add(
                    project_id=project_id,
                    run_id=run_id,
                    node_id=node_id,
                    kind=artifact_input.kind,
                    path=artifact_input.path,
                    media_type=artifact_input.media_type,
                    sha256=artifact_input.sha256,
                    size_bytes=artifact_input.size_bytes,
                    artifact_metadata=artifact_input.artifact_metadata,
                    created_at=created_at,
                )
                persisted_artifacts.append(artifact)
                persisted_events.append(
                    await _add_artifact_created_event(
                        events=unit_of_work.events,
                        project_id=project_id,
                        run_id=run_id,
                        node_id=node_id,
                        artifact=artifact,
                        created_at=created_at,
                    )
                )
                await unit_of_work.outbox.add_from_event(persisted_events[-1])
            await unit_of_work.commit()
        return tuple(persisted_artifacts), tuple(persisted_events)

    async def _artifact_input(
        self,
        *,
        kind: ArtifactKind,
        path: Path,
        media_type: str,
        metadata: dict[str, object],
    ) -> ArtifactInput | None:
        if not path.is_file():
            return None
        sha256, size_bytes = await asyncio.to_thread(_hash_file, path)
        return ArtifactInput(
            kind=kind,
            path=str(path),
            media_type=media_type,
            sha256=sha256,
            size_bytes=size_bytes,
            artifact_metadata=metadata,
        )


async def _add_artifact_created_event(
    *,
    events: EventRepository,
    project_id: UUID,
    run_id: UUID | None,
    node_id: UUID | None,
    artifact: Artifact,
    created_at: datetime,
) -> EventRecord:
    return await events.add(
        project_id=project_id,
        topic=EventTopic.ARTIFACT_CREATED,
        payload={
            "projectId": str(project_id),
            "runId": str(run_id) if run_id is not None else None,
            "nodeId": str(node_id) if node_id is not None else None,
            "artifactId": str(artifact.id),
            "kind": artifact.kind.value,
            "path": artifact.path,
            "sha256": artifact.sha256,
            "sizeBytes": artifact.size_bytes,
        },
        created_at=created_at,
    )


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            size_bytes += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size_bytes
