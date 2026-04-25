from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.domain.enums import EventTopic, NodeKind, NodeStatus
from agentsofchaos_orchestrator.domain.errors import (
    ProjectNotFoundError,
    RootNodeAlreadyExistsError,
)
from agentsofchaos_orchestrator.domain.models import CodeSnapshot, ContextSnapshot, Node, Project
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


class ProjectNodeService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        git_service: GitService,
        events: ApplicationEventRecorder,
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._settings = settings
        self._git_service = git_service
        self._events = events
        self._now = now
        self._new_uuid = new_uuid

    async def open_project(self, root_path: Path) -> Project:
        repository = self._git_service.inspect_repository(root_path)
        daemon_state_dir = self._settings.daemon_state_dir_for_project(repository.root_path)
        _ensure_project_state_directories(daemon_state_dir)

        async with self._unit_of_work() as unit_of_work:
            existing = await unit_of_work.projects.get_by_root_path(str(repository.root_path))
            if existing is not None:
                return existing

            project = await unit_of_work.projects.add(
                root_path=str(repository.root_path),
                git_dir=str(repository.git_dir),
            )
            await unit_of_work.commit()

        await self._events.record_and_publish(
            project_id=project.id,
            topic=EventTopic.PROJECT_OPENED,
            payload={
                "project_id": str(project.id),
                "root_path": project.root_path,
                "git_dir": project.git_dir,
            },
            created_at=self._now(),
        )
        return project

    async def create_root_node(self, project_id: UUID, title: str | None = None) -> Node:
        async with self._unit_of_work() as unit_of_work:
            project = await unit_of_work.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Unknown project: {project_id}")
            if await unit_of_work.nodes.has_root_node(project_id):
                raise RootNodeAlreadyExistsError(f"Project {project_id} already has a root node")

            head_commit = self._git_service.current_head_commit(Path(project.root_path))
            timestamp = self._now()
            code_snapshot = await unit_of_work.code_snapshots.add(
                project_id=project.id,
                commit_sha=head_commit,
                git_ref=None,
            )
            context_snapshot = ContextSnapshot(
                id=self._new_uuid(),
                project_id=project.id,
                summary="Root context created from repository HEAD.",
                created_at=timestamp,
            )
            persisted_context = await unit_of_work.context_snapshots.add(context_snapshot)
            node = await unit_of_work.nodes.add(
                project_id=project.id,
                kind=NodeKind.ROOT,
                parent_node_ids=(),
                code_snapshot_id=code_snapshot.id,
                context_snapshot_id=persisted_context.id,
                status=NodeStatus.READY,
                title=title or f"Root @ {head_commit[:12]}",
                created_at=timestamp,
            )
            await unit_of_work.commit()

        ref_name = f"{self._settings.node_ref_prefix}/{node.id}"
        self._git_service.ensure_node_ref(
            Path(project.root_path),
            ref_name=ref_name,
            commit_sha=head_commit,
        )
        code_snapshot = await self._update_code_snapshot_git_ref(
            code_snapshot.id,
            git_ref=ref_name,
        )
        await self._events.record_and_publish(
            project_id=project.id,
            topic=EventTopic.ROOT_NODE_CREATED,
            payload={
                "project_id": str(project.id),
                "node_id": str(node.id),
                "code_snapshot_id": str(code_snapshot.id),
                "context_snapshot_id": str(persisted_context.id),
                "commit_sha": head_commit,
                "git_ref": ref_name,
                "title": node.title,
            },
            created_at=timestamp,
        )
        return node

    async def _update_code_snapshot_git_ref(
        self,
        snapshot_id: UUID,
        *,
        git_ref: str,
    ) -> CodeSnapshot:
        async with self._unit_of_work() as unit_of_work:
            snapshot = await unit_of_work.code_snapshots.update_git_ref(
                snapshot_id,
                git_ref=git_ref,
            )
            await unit_of_work.commit()
            return snapshot


def _ensure_project_state_directories(daemon_state_dir: Path) -> None:
    daemon_state_dir.mkdir(parents=True, exist_ok=True)
    (daemon_state_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (daemon_state_dir / "runs").mkdir(parents=True, exist_ok=True)
    (daemon_state_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    (daemon_state_dir / "worktrees").mkdir(parents=True, exist_ok=True)
