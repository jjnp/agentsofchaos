from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.domain.errors import (
    NodeNotFoundError,
    ProjectNotFoundError,
    RunNotFoundError,
    SnapshotNotFoundError,
)
from agentsofchaos_orchestrator.domain.models import (
    CodeSnapshot,
    ContextSnapshot,
    EventRecord,
    GraphSnapshot,
    Node,
    Run,
)
from agentsofchaos_orchestrator.infrastructure.repositories import build_graph_snapshot
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


class QueryService:
    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._unit_of_work = UnitOfWorkFactory(session_factory)

    async def get_run(self, run_id: UUID) -> Run:
        async with self._unit_of_work() as unit_of_work:
            run = await unit_of_work.runs.get(run_id)
            if run is None:
                raise RunNotFoundError(f"Unknown run: {run_id}")
            return run

    async def get_node(self, *, project_id: UUID, node_id: UUID) -> Node:
        async with self._unit_of_work() as unit_of_work:
            node = await unit_of_work.nodes.get(node_id)
            if node is None or node.project_id != project_id:
                raise NodeNotFoundError(
                    f"Node {node_id} does not belong to project {project_id}"
                )
            return node

    async def get_code_snapshot(
        self, *, project_id: UUID, snapshot_id: UUID
    ) -> CodeSnapshot:
        async with self._unit_of_work() as unit_of_work:
            snapshot = await unit_of_work.code_snapshots.get(snapshot_id)
            if snapshot is None or snapshot.project_id != project_id:
                raise SnapshotNotFoundError(
                    f"Code snapshot {snapshot_id} does not belong to project {project_id}"
                )
            return snapshot

    async def get_context_snapshot(
        self, *, project_id: UUID, snapshot_id: UUID
    ) -> ContextSnapshot:
        async with self._unit_of_work() as unit_of_work:
            snapshot = await unit_of_work.context_snapshots.get(snapshot_id)
            if snapshot is None or snapshot.project_id != project_id:
                raise SnapshotNotFoundError(
                    f"Context snapshot {snapshot_id} does not belong to project {project_id}"
                )
            return snapshot

    async def get_graph(self, project_id: UUID) -> GraphSnapshot:
        async with self._session_factory() as session:
            graph = await build_graph_snapshot(session, project_id)
            if graph is None:
                raise ProjectNotFoundError(f"Unknown project: {project_id}")
            return graph

    async def list_events(self, project_id: UUID) -> tuple[EventRecord, ...]:
        async with self._unit_of_work() as unit_of_work:
            project = await unit_of_work.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Unknown project: {project_id}")
            return await unit_of_work.events.list_by_project(project_id)
