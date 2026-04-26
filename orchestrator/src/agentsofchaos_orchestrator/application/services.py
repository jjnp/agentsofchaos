from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.artifacts import ArtifactRecorder
from agentsofchaos_orchestrator.application.context_diff import (
    ContextDiff,
    ContextDiffApplicationService,
)
from agentsofchaos_orchestrator.application.diffs import DiffApplicationService, NodeDiff
from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.application.merges import (
    MergeApplicationService,
    MergeNodeResult,
)
from agentsofchaos_orchestrator.application.outbox_worker import OutboxDispatchWorker
from agentsofchaos_orchestrator.application.project_nodes import ProjectNodeService
from agentsofchaos_orchestrator.application.queries import QueryService
from agentsofchaos_orchestrator.application.recovery import StartupRecoveryService
from agentsofchaos_orchestrator.application.runs import RunApplicationService
from agentsofchaos_orchestrator.domain.enums import SandboxKind
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
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.runtime import NoOpRuntimeAdapter, RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.settings import Settings


class OrchestratorService:
    """Facade preserving the public application API while responsibilities are split."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        git_service: GitService,
        event_bus: InMemoryEventBus,
        runtime_adapter: RuntimeAdapter | None = None,
        sandbox_kind: SandboxKind = SandboxKind.NONE,
        now: Callable[[], datetime] | None = None,
        new_uuid: Callable[[], UUID] | None = None,
    ) -> None:
        clock = now or (lambda: datetime.now(UTC))
        uuid_factory = new_uuid or uuid4
        runtime = runtime_adapter or NoOpRuntimeAdapter()
        events = ApplicationEventRecorder(
            session_factory=session_factory,
            event_bus=event_bus,
            now=clock,
            new_uuid=uuid_factory,
        )
        artifact_recorder = ArtifactRecorder(
            session_factory=session_factory,
            event_bus=event_bus,
            now=clock,
        )
        self._project_nodes = ProjectNodeService(
            session_factory=session_factory,
            settings=settings,
            git_service=git_service,
            events=events,
            now=clock,
            new_uuid=uuid_factory,
        )
        self._runs = RunApplicationService(
            session_factory=session_factory,
            settings=settings,
            git_service=git_service,
            runtime_adapter=runtime,
            artifact_recorder=artifact_recorder,
            events=events,
            now=clock,
            new_uuid=uuid_factory,
            sandbox_kind=sandbox_kind,
        )
        self._merges = MergeApplicationService(
            session_factory=session_factory,
            settings=settings,
            git_service=git_service,
            artifact_recorder=artifact_recorder,
            events=events,
            now=clock,
            new_uuid=uuid_factory,
        )
        self._recovery = StartupRecoveryService(
            session_factory=session_factory,
            settings=settings,
            git_service=git_service,
            events=events,
            now=clock,
        )
        self._outbox_worker = OutboxDispatchWorker(events=events)
        self._queries = QueryService(session_factory=session_factory)
        self._git_service = git_service
        self._diffs = DiffApplicationService(
            session_factory=session_factory,
            git_service=git_service,
            queries=self._queries,
        )
        self._context_diffs = ContextDiffApplicationService(
            session_factory=session_factory,
            queries=self._queries,
        )

    async def start_background_workers(self) -> None:
        await self._outbox_worker.start()

    async def reconcile_startup(self) -> int:
        reconciled = await self._recovery.reconcile_interrupted_runs()
        await self._recovery.cleanup_stale_worktrees()
        return reconciled

    async def open_project(self, root_path: Path) -> Project:
        return await self._project_nodes.open_project(root_path)

    async def create_root_node(self, project_id: UUID, title: str | None = None) -> Node:
        return await self._project_nodes.create_root_node(project_id, title=title)

    async def run_prompt(
        self,
        node_id: UUID,
        prompt: str,
        title: str | None = None,
    ) -> tuple[Run, Node]:
        return await self._runs.run_prompt(node_id=node_id, prompt=prompt, title=title)

    async def start_prompt_run(self, node_id: UUID, prompt: str) -> Run:
        return await self._runs.start_prompt_run(node_id=node_id, prompt=prompt)

    async def run_merge_resolution_prompt(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        prompt: str,
        title: str | None = None,
    ) -> tuple[Run, Node]:
        return await self._runs.run_merge_resolution_prompt(
            project_id=project_id,
            merge_node_id=merge_node_id,
            prompt=prompt,
            title=title,
        )

    async def start_merge_resolution_prompt_run(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        prompt: str,
    ) -> Run:
        return await self._runs.start_merge_resolution_prompt_run(
            project_id=project_id,
            merge_node_id=merge_node_id,
            prompt=prompt,
        )

    async def merge_nodes(
        self,
        *,
        project_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        title: str | None = None,
    ) -> MergeNodeResult:
        return await self._merges.merge_nodes(
            project_id=project_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            title=title,
        )

    async def get_merge_report(self, *, project_id: UUID, node_id: UUID) -> dict[str, object]:
        return await self._merges.get_merge_report(project_id=project_id, node_id=node_id)

    async def cancel_run(self, run_id: UUID) -> bool:
        return await self._runs.cancel_run(run_id)

    async def shutdown(self) -> None:
        await self._runs.shutdown()
        await self._outbox_worker.stop()

    async def get_run(self, run_id: UUID) -> Run:
        return await self._queries.get_run(run_id)

    async def get_node(self, *, project_id: UUID, node_id: UUID) -> Node:
        return await self._queries.get_node(project_id=project_id, node_id=node_id)

    async def get_code_snapshot(
        self, *, project_id: UUID, snapshot_id: UUID
    ) -> CodeSnapshot:
        return await self._queries.get_code_snapshot(
            project_id=project_id, snapshot_id=snapshot_id
        )

    async def get_context_snapshot(
        self, *, project_id: UUID, snapshot_id: UUID
    ) -> ContextSnapshot:
        return await self._queries.get_context_snapshot(
            project_id=project_id, snapshot_id=snapshot_id
        )

    async def get_node_diff(self, *, project_id: UUID, node_id: UUID) -> NodeDiff:
        return await self._diffs.get_node_diff(project_id=project_id, node_id=node_id)

    async def read_node_file(
        self, *, project_id: UUID, node_id: UUID, path: str
    ) -> bytes:
        """Return raw bytes of `path` at this node's code snapshot.

        Resolves the chain node → code_snapshot → commit_sha, then
        reads the blob from the project's git repository. Used by the
        download endpoint so a viewer can pull any agent-touched file
        out without scripting against the daemon.
        """
        node = await self._queries.get_node(project_id=project_id, node_id=node_id)
        snapshot = await self._queries.get_code_snapshot(
            project_id=project_id, snapshot_id=node.code_snapshot_id
        )
        project = await self._queries.get_project(project_id)
        return self._git_service.read_file_at(
            Path(project.root_path),
            commit_sha=snapshot.commit_sha,
            path=path,
        )

    async def archive_node(
        self, *, project_id: UUID, node_id: UUID
    ) -> tuple[bytes, str]:
        """Return a tar of the full tree at this node's commit, plus
        the short commit SHA so the route can compose a sensible
        download filename.
        """
        node = await self._queries.get_node(project_id=project_id, node_id=node_id)
        snapshot = await self._queries.get_code_snapshot(
            project_id=project_id, snapshot_id=node.code_snapshot_id
        )
        project = await self._queries.get_project(project_id)
        archive = self._git_service.archive_at(
            Path(project.root_path),
            commit_sha=snapshot.commit_sha,
        )
        return archive, snapshot.commit_sha

    async def get_node_context_diff(
        self, *, project_id: UUID, node_id: UUID
    ) -> ContextDiff:
        return await self._context_diffs.get_node_context_diff(
            project_id=project_id, node_id=node_id
        )

    async def get_graph(self, project_id: UUID) -> GraphSnapshot:
        return await self._queries.get_graph(project_id)

    async def list_events(self, project_id: UUID) -> tuple[EventRecord, ...]:
        return await self._queries.list_events(project_id)

    async def list_events_since(
        self,
        project_id: UUID,
        *,
        after_event_id: UUID,
    ) -> tuple[EventRecord, ...] | None:
        return await self._queries.list_events_since(
            project_id, after_event_id=after_event_id
        )

    async def list_artifacts(
        self,
        project_id: UUID,
        *,
        node_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> tuple[Artifact, ...]:
        return await self._queries.list_artifacts(
            project_id, node_id=node_id, run_id=run_id
        )

    async def get_artifact(
        self, *, project_id: UUID, artifact_id: UUID
    ) -> Artifact:
        return await self._queries.get_artifact(
            project_id=project_id, artifact_id=artifact_id
        )
