from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agentsofchaos_orchestrator.domain.enums import (
    ArtifactKind,
    EventTopic,
    NodeKind,
    NodeStatus,
    RunStatus,
    RuntimeKind,
    SandboxKind,
)
from agentsofchaos_orchestrator.domain.models import (
    Artifact,
    CodeSnapshot,
    ContextSnapshot,
    EventRecord,
    GraphSnapshot,
    Node,
    Project,
    Run,
)
from agentsofchaos_orchestrator.infrastructure.orm import (
    ArtifactRecord,
    CodeSnapshotRecord,
    ContextSnapshotRecord,
    EventRecordORM,
    NodeRecord,
    OutboxEventRecord,
    ProjectRecord,
    RunRecord,
)


def _utc(value: datetime) -> datetime:
    """Re-attach UTC tzinfo when SQLite drops it on read.

    All datetime columns are declared `DateTime(timezone=True)` and writes use
    `datetime.now(timezone.utc)`, but SQLite's TEXT-based storage discards tz so
    SQLAlchemy returns a naive datetime. We assume UTC at the repo boundary so
    domain models and JSON responses always carry a tz.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    return _utc(value) if value is not None else None


def _to_project(record: ProjectRecord) -> Project:
    return Project(
        id=UUID(record.id),
        root_path=record.root_path,
        git_dir=record.git_dir,
        created_at=_utc(record.created_at),
        updated_at=_utc(record.updated_at),
    )


def _to_code_snapshot(record: CodeSnapshotRecord) -> CodeSnapshot:
    return CodeSnapshot(
        id=UUID(record.id),
        project_id=UUID(record.project_id),
        commit_sha=record.commit_sha,
        git_ref=record.git_ref,
        created_at=_utc(record.created_at),
    )


def _to_context_snapshot(record: ContextSnapshotRecord) -> ContextSnapshot:
    return ContextSnapshot.model_validate(
        {
            "id": record.id,
            "project_id": record.project_id,
            "parent_ids": record.parent_ids,
            "transcript_ref": record.transcript_ref,
            "summary": record.summary,
            "goals": record.goals,
            "constraints": record.constraints,
            "decisions": record.decisions,
            "assumptions": record.assumptions,
            "open_questions": record.open_questions,
            "todos": record.todos,
            "risks": record.risks,
            "handoff_notes": record.handoff_notes,
            "read_files": record.read_files,
            "touched_files": record.touched_files,
            "symbols": record.symbols,
            "merge_metadata": record.merge_metadata,
            "created_at": _utc(record.created_at),
        }
    )


def _to_node(record: NodeRecord) -> Node:
    return Node(
        id=UUID(record.id),
        project_id=UUID(record.project_id),
        kind=NodeKind(record.kind),
        parent_node_ids=tuple(UUID(value) for value in record.parent_node_ids),
        code_snapshot_id=UUID(record.code_snapshot_id),
        context_snapshot_id=UUID(record.context_snapshot_id),
        status=NodeStatus(record.status),
        title=record.title,
        created_at=_utc(record.created_at),
        originating_run_id=UUID(record.originating_run_id) if record.originating_run_id else None,
    )


def _to_run(record: RunRecord) -> Run:
    return Run(
        id=UUID(record.id),
        project_id=UUID(record.project_id),
        source_node_id=UUID(record.source_node_id),
        prompt=record.prompt,
        planned_child_node_id=(
            UUID(record.planned_child_node_id)
            if record.planned_child_node_id
            else None
        ),
        status=RunStatus(record.status),
        runtime=RuntimeKind(record.runtime),
        sandbox=SandboxKind(record.sandbox),
        worktree_path=record.worktree_path,
        transcript_path=record.transcript_path,
        error_message=record.error_message,
        started_at=_utc_or_none(record.started_at),
        finished_at=_utc_or_none(record.finished_at),
    )


def _to_event(record: EventRecordORM) -> EventRecord:
    return EventRecord(
        id=UUID(record.id),
        project_id=UUID(record.project_id),
        topic=EventTopic(record.topic),
        payload=record.payload,
        created_at=_utc(record.created_at),
    )


def _to_artifact(record: ArtifactRecord) -> Artifact:
    return Artifact(
        id=UUID(record.id),
        project_id=UUID(record.project_id),
        run_id=UUID(record.run_id) if record.run_id is not None else None,
        node_id=UUID(record.node_id) if record.node_id is not None else None,
        kind=ArtifactKind(record.kind),
        path=record.path,
        media_type=record.media_type,
        sha256=record.sha256,
        size_bytes=record.size_bytes,
        artifact_metadata=record.artifact_metadata,
        created_at=_utc(record.created_at),
    )


def _outbox_to_event(record: OutboxEventRecord) -> EventRecord:
    return EventRecord(
        id=UUID(record.event_record_id),
        project_id=UUID(record.project_id),
        topic=EventTopic(record.topic),
        payload=record.payload,
        created_at=_utc(record.created_at),
    )


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: UUID) -> Project | None:
        record = await self._session.get(ProjectRecord, str(project_id))
        return _to_project(record) if record is not None else None

    async def get_by_root_path(self, root_path: str) -> Project | None:
        statement = select(ProjectRecord).where(ProjectRecord.root_path == root_path)
        record = await self._session.scalar(statement)
        return _to_project(record) if record is not None else None

    async def list_all(self) -> tuple[Project, ...]:
        statement: Select[tuple[ProjectRecord]] = select(ProjectRecord).order_by(
            ProjectRecord.created_at.asc()
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_project(record) for record in records)

    async def add(self, *, root_path: str, git_dir: str) -> Project:
        record = ProjectRecord(id=str(uuid4()), root_path=root_path, git_dir=git_dir)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_project(record)


class CodeSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, snapshot_id: UUID) -> CodeSnapshot | None:
        record = await self._session.get(CodeSnapshotRecord, str(snapshot_id))
        return _to_code_snapshot(record) if record is not None else None

    async def add(self, *, project_id: UUID, commit_sha: str, git_ref: str | None) -> CodeSnapshot:
        record = CodeSnapshotRecord(
            id=str(uuid4()),
            project_id=str(project_id),
            commit_sha=commit_sha,
            git_ref=git_ref,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_code_snapshot(record)

    async def update_git_ref(self, snapshot_id: UUID, *, git_ref: str) -> CodeSnapshot:
        record = await self._session.get(CodeSnapshotRecord, str(snapshot_id))
        if record is None:
            raise ValueError(f"Unknown code snapshot: {snapshot_id}")
        record.git_ref = git_ref
        await self._session.flush()
        await self._session.refresh(record)
        return _to_code_snapshot(record)


class ContextSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, snapshot_id: UUID) -> ContextSnapshot | None:
        record = await self._session.get(ContextSnapshotRecord, str(snapshot_id))
        return _to_context_snapshot(record) if record is not None else None

    async def list_by_project(self, project_id: UUID) -> tuple[ContextSnapshot, ...]:
        statement: Select[tuple[ContextSnapshotRecord]] = (
            select(ContextSnapshotRecord)
            .where(ContextSnapshotRecord.project_id == str(project_id))
            .order_by(ContextSnapshotRecord.created_at.asc())
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_context_snapshot(record) for record in records)

    async def add(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        record = ContextSnapshotRecord(
            id=str(snapshot.id),
            project_id=str(snapshot.project_id),
            parent_ids=[str(value) for value in snapshot.parent_ids],
            transcript_ref=snapshot.transcript_ref,
            summary=snapshot.summary,
            goals=[item.model_dump(mode="json") for item in snapshot.goals],
            constraints=[item.model_dump(mode="json") for item in snapshot.constraints],
            decisions=[item.model_dump(mode="json") for item in snapshot.decisions],
            assumptions=[item.model_dump(mode="json") for item in snapshot.assumptions],
            open_questions=[item.model_dump(mode="json") for item in snapshot.open_questions],
            todos=[item.model_dump(mode="json") for item in snapshot.todos],
            risks=[item.model_dump(mode="json") for item in snapshot.risks],
            handoff_notes=[item.model_dump(mode="json") for item in snapshot.handoff_notes],
            read_files=[item.model_dump(mode="json") for item in snapshot.read_files],
            touched_files=[item.model_dump(mode="json") for item in snapshot.touched_files],
            symbols=[item.model_dump(mode="json") for item in snapshot.symbols],
            merge_metadata=snapshot.merge_metadata.model_dump(mode="json")
            if snapshot.merge_metadata is not None
            else None,
            created_at=snapshot.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_context_snapshot(record)


class NodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, node_id: UUID) -> Node | None:
        record = await self._session.get(NodeRecord, str(node_id))
        return _to_node(record) if record is not None else None

    async def list_by_project(self, project_id: UUID) -> tuple[Node, ...]:
        statement = (
            select(NodeRecord)
            .where(NodeRecord.project_id == str(project_id))
            .order_by(NodeRecord.created_at.asc())
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_node(record) for record in records)

    async def get_root_node(self, project_id: UUID) -> Node | None:
        statement = select(NodeRecord).where(
            NodeRecord.project_id == str(project_id),
            NodeRecord.kind == NodeKind.ROOT.value,
        )
        record = await self._session.scalar(statement)
        return _to_node(record) if record is not None else None

    async def has_root_node(self, project_id: UUID) -> bool:
        return await self.get_root_node(project_id) is not None

    async def add(
        self,
        *,
        project_id: UUID,
        kind: NodeKind,
        parent_node_ids: Sequence[UUID],
        code_snapshot_id: UUID,
        context_snapshot_id: UUID,
        status: NodeStatus,
        title: str,
        created_at: datetime,
        originating_run_id: UUID | None = None,
        node_id: UUID | None = None,
    ) -> Node:
        record = NodeRecord(
            id=str(node_id or uuid4()),
            project_id=str(project_id),
            kind=kind.value,
            parent_node_ids=[str(value) for value in parent_node_ids],
            code_snapshot_id=str(code_snapshot_id),
            context_snapshot_id=str(context_snapshot_id),
            status=status.value,
            title=title,
            created_at=created_at,
            originating_run_id=str(originating_run_id) if originating_run_id is not None else None,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_node(record)


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: Run) -> Run:
        record = RunRecord(
            id=str(run.id),
            project_id=str(run.project_id),
            source_node_id=str(run.source_node_id),
            prompt=run.prompt,
            planned_child_node_id=str(run.planned_child_node_id)
            if run.planned_child_node_id is not None
            else None,
            status=run.status.value,
            runtime=run.runtime.value,
            sandbox=run.sandbox.value,
            worktree_path=run.worktree_path,
            transcript_path=run.transcript_path,
            error_message=run.error_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_run(record)

    async def get(self, run_id: UUID) -> Run | None:
        record = await self._session.get(RunRecord, str(run_id))
        return _to_run(record) if record is not None else None

    async def list_by_statuses(self, statuses: Sequence[RunStatus]) -> tuple[Run, ...]:
        status_values = [status.value for status in statuses]
        if not status_values:
            return ()
        statement: Select[tuple[RunRecord]] = (
            select(RunRecord)
            .where(RunRecord.status.in_(status_values))
            .order_by(RunRecord.started_at.asc(), RunRecord.id.asc())
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_run(record) for record in records)

    async def update(self, run: Run) -> Run:
        record = await self._session.get(RunRecord, str(run.id))
        if record is None:
            raise ValueError(f"Unknown run: {run.id}")

        record.prompt = run.prompt
        record.status = run.status.value
        record.runtime = run.runtime.value
        record.sandbox = run.sandbox.value
        record.worktree_path = run.worktree_path
        record.transcript_path = run.transcript_path
        record.error_message = run.error_message
        record.started_at = run.started_at
        record.finished_at = run.finished_at
        record.planned_child_node_id = (
            str(run.planned_child_node_id) if run.planned_child_node_id is not None else None
        )
        await self._session.flush()
        await self._session.refresh(record)
        return _to_run(record)


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        project_id: UUID,
        kind: ArtifactKind,
        path: str,
        media_type: str,
        sha256: str,
        size_bytes: int,
        created_at: datetime,
        run_id: UUID | None = None,
        node_id: UUID | None = None,
        artifact_metadata: dict[str, object] | None = None,
    ) -> Artifact:
        record = ArtifactRecord(
            id=str(uuid4()),
            project_id=str(project_id),
            run_id=str(run_id) if run_id is not None else None,
            node_id=str(node_id) if node_id is not None else None,
            kind=kind.value,
            path=path,
            media_type=media_type,
            sha256=sha256,
            size_bytes=size_bytes,
            artifact_metadata=artifact_metadata or {},
            created_at=created_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_artifact(record)

    async def list_by_run(self, run_id: UUID) -> tuple[Artifact, ...]:
        statement: Select[tuple[ArtifactRecord]] = (
            select(ArtifactRecord)
            .where(ArtifactRecord.run_id == str(run_id))
            .order_by(ArtifactRecord.created_at.asc())
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_artifact(record) for record in records)

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        node_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> tuple[Artifact, ...]:
        statement: Select[tuple[ArtifactRecord]] = (
            select(ArtifactRecord)
            .where(ArtifactRecord.project_id == str(project_id))
            .order_by(ArtifactRecord.created_at.asc())
        )
        if node_id is not None:
            statement = statement.where(ArtifactRecord.node_id == str(node_id))
        if run_id is not None:
            statement = statement.where(ArtifactRecord.run_id == str(run_id))
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_artifact(record) for record in records)

    async def get(self, artifact_id: UUID) -> Artifact | None:
        record = await self._session.get(ArtifactRecord, str(artifact_id))
        return _to_artifact(record) if record is not None else None


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_from_event(self, event: EventRecord) -> None:
        record = OutboxEventRecord(
            id=str(uuid4()),
            event_record_id=str(event.id),
            project_id=str(event.project_id),
            topic=event.topic.value,
            payload=event.payload,
            created_at=event.created_at,
            published_at=None,
        )
        self._session.add(record)
        await self._session.flush()

    async def get_unpublished_event(self, event_record_id: UUID) -> EventRecord | None:
        statement = select(OutboxEventRecord).where(
            OutboxEventRecord.event_record_id == str(event_record_id),
            OutboxEventRecord.published_at.is_(None),
        )
        record = await self._session.scalar(statement)
        return _outbox_to_event(record) if record is not None else None

    async def list_unpublished(self, *, limit: int = 100) -> tuple[EventRecord, ...]:
        statement: Select[tuple[OutboxEventRecord]] = (
            select(OutboxEventRecord)
            .where(OutboxEventRecord.published_at.is_(None))
            .order_by(OutboxEventRecord.created_at.asc())
            .limit(limit)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_outbox_to_event(record) for record in records)

    async def mark_published(self, event_record_id: UUID, *, published_at: datetime) -> bool:
        """
        Atomically claim an outbox row by transitioning it from unpublished to published.
        Returns True if this call was the one that transitioned the row, False otherwise
        (row missing or already published). Used to serialise concurrent dispatch paths
        (inline record_and_publish vs OutboxDispatchWorker) so only one delivers each event.
        """
        statement = (
            update(OutboxEventRecord)
            .where(
                OutboxEventRecord.event_record_id == str(event_record_id),
                OutboxEventRecord.published_at.is_(None),
            )
            .values(published_at=published_at)
        )
        result = await self._session.execute(statement)
        await self._session.flush()
        rowcount = getattr(result, "rowcount", 0) or 0
        return rowcount > 0


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: UUID) -> EventRecord | None:
        record = await self._session.get(EventRecordORM, str(event_id))
        return _to_event(record) if record is not None else None

    async def add(
        self,
        *,
        project_id: UUID,
        topic: EventTopic,
        payload: dict[str, object],
        created_at: datetime,
    ) -> EventRecord:
        record = EventRecordORM(
            id=str(uuid4()),
            project_id=str(project_id),
            topic=topic.value,
            payload=payload,
            created_at=created_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_event(record)

    async def list_by_project(self, project_id: UUID) -> tuple[EventRecord, ...]:
        statement: Select[tuple[EventRecordORM]] = (
            select(EventRecordORM)
            .where(EventRecordORM.project_id == str(project_id))
            .order_by(EventRecordORM.created_at.asc())
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_event(record) for record in records)


async def build_graph_snapshot(session: AsyncSession, project_id: UUID) -> GraphSnapshot | None:
    project = await ProjectRepository(session).get(project_id)
    if project is None:
        return None

    nodes = await NodeRepository(session).list_by_project(project_id)
    return GraphSnapshot(project=project, nodes=nodes)
