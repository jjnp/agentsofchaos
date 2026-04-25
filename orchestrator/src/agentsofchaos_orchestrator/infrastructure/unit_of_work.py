from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.infrastructure.repositories import (
    ArtifactRepository,
    CodeSnapshotRepository,
    ContextSnapshotRepository,
    EventRepository,
    NodeRepository,
    OutboxRepository,
    ProjectRepository,
    RunRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.projects = ProjectRepository(self._session)
        self.code_snapshots = CodeSnapshotRepository(self._session)
        self.context_snapshots = ContextSnapshotRepository(self._session)
        self.nodes = NodeRepository(self._session)
        self.runs = RunRepository(self._session)
        self.artifacts = ArtifactRepository(self._session)
        self.events = EventRepository(self._session)
        self.outbox = OutboxRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        session = self._require_session()
        try:
            if not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._committed = False

    async def commit(self) -> None:
        await self._require_session().commit()
        self._committed = True

    async def rollback(self) -> None:
        await self._require_session().rollback()
        self._committed = False

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered")
        return self._session

    projects: ProjectRepository
    code_snapshots: CodeSnapshotRepository
    context_snapshots: ContextSnapshotRepository
    nodes: NodeRepository
    runs: RunRepository
    artifacts: ArtifactRepository
    events: EventRepository
    outbox: OutboxRepository


class UnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)
