from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.artifacts import ArtifactRecorder
from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.domain.enums import EventTopic, NodeKind, RunStatus, RuntimeKind
from agentsofchaos_orchestrator.domain.models import (
    CodeSnapshot,
    ContextSnapshot,
    Node,
    Project,
    Run,
)
from agentsofchaos_orchestrator.domain.run_policy import RunLifecyclePolicy
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


class RunStateService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        artifact_recorder: ArtifactRecorder,
        events: ApplicationEventRecorder,
        now: Callable[[], datetime],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._artifact_recorder = artifact_recorder
        self._events = events
        self._now = now
        self._lifecycle = RunLifecyclePolicy()

    async def create_queued_run(
        self,
        *,
        project: Project,
        source_node: Node,
        run_id: UUID,
        child_node_id: UUID,
        prompt: str,
        runtime: RuntimeKind,
        worktree_path: Path,
        created_at: datetime,
    ) -> Run:
        run = Run(
            id=run_id,
            project_id=project.id,
            source_node_id=source_node.id,
            prompt=prompt,
            planned_child_node_id=child_node_id,
            status=RunStatus.QUEUED,
            runtime=runtime,
            worktree_path=str(worktree_path),
        )
        run = await self.persist_run(run)
        await self._events.record_and_publish(
            project_id=project.id,
            topic=EventTopic.RUN_CREATED,
            payload={
                "project_id": str(project.id),
                "run_id": str(run.id),
                "source_node_id": str(source_node.id),
                "planned_child_node_id": str(child_node_id),
                "prompt": prompt,
            },
            created_at=created_at,
        )
        return run

    async def start_run(self, run: Run, *, worktree_path: Path, started_at: datetime) -> Run:
        running_run = self._lifecycle.start(run, started_at=started_at)
        running_run = await self.persist_run(running_run)
        await self._events.record_and_publish(
            project_id=running_run.project_id,
            topic=EventTopic.RUN_STARTED,
            payload={
                "project_id": str(running_run.project_id),
                "run_id": str(running_run.id),
                "worktree_path": str(worktree_path),
            },
            created_at=started_at,
        )
        return running_run

    async def succeed_run(
        self,
        *,
        running_run: Run,
        child_node: Node,
        child_code_snapshot: CodeSnapshot,
        child_context_snapshot: ContextSnapshot,
        committed_sha: str,
        git_ref: str,
        child_created_at: datetime,
        transcript_path: Path,
        runtime_metadata: dict[str, object],
    ) -> Run:
        succeeded_run = self._lifecycle.succeed(
            running_run,
            transcript_path=str(transcript_path),
            finished_at=self._now(),
        )
        succeeded_run = await self.persist_run(succeeded_run)
        await self._record_child_node_created(
            succeeded_run=succeeded_run,
            child_node=child_node,
            child_code_snapshot=child_code_snapshot,
            child_context_snapshot=child_context_snapshot,
            committed_sha=committed_sha,
            git_ref=git_ref,
            child_created_at=child_created_at,
        )
        artifacts = await self._artifact_recorder.record_run_artifacts(
            project_id=succeeded_run.project_id,
            run_id=succeeded_run.id,
            node_id=child_node.id,
            transcript_path=transcript_path,
            runtime_metadata=runtime_metadata,
            created_at=succeeded_run.finished_at or child_created_at,
        )
        await self._events.record_and_publish(
            project_id=succeeded_run.project_id,
            topic=EventTopic.RUN_SUCCEEDED,
            payload={
                "project_id": str(succeeded_run.project_id),
                "run_id": str(succeeded_run.id),
                "child_node_id": str(child_node.id),
                "transcript_path": str(transcript_path),
                "artifact_ids": [str(artifact.id) for artifact in artifacts],
                "runtime_metadata": runtime_metadata,
            },
            created_at=succeeded_run.finished_at or child_created_at,
        )
        return succeeded_run

    async def cancel_run(
        self,
        running_run: Run,
        *,
        transcript_path: Path | None = None,
        runtime_metadata: dict[str, object] | None = None,
    ) -> Run:
        cancelled_run = self._lifecycle.cancel(
            running_run,
            transcript_path=str(transcript_path) if transcript_path is not None else None,
            finished_at=self._now(),
        )
        cancelled_run = await self.persist_run(cancelled_run)
        artifacts = ()
        if transcript_path is not None:
            artifacts = await self._artifact_recorder.record_run_artifacts(
                project_id=cancelled_run.project_id,
                run_id=cancelled_run.id,
                node_id=None,
                transcript_path=transcript_path,
                runtime_metadata=runtime_metadata or {},
                created_at=cancelled_run.finished_at or self._now(),
            )
        await self._events.record_and_publish(
            project_id=cancelled_run.project_id,
            topic=EventTopic.RUN_CANCELLED,
            payload={
                "project_id": str(cancelled_run.project_id),
                "run_id": str(cancelled_run.id),
                "cancelled": True,
                "transcript_path": str(transcript_path) if transcript_path is not None else None,
                "artifact_ids": [str(artifact.id) for artifact in artifacts],
            },
            created_at=cancelled_run.finished_at or self._now(),
        )
        return cancelled_run

    async def fail_run(self, running_run: Run, *, error: Exception) -> Run:
        failed_run = self._lifecycle.fail(
            running_run,
            error_message=str(error),
            finished_at=self._now(),
        )
        failed_run = await self.persist_run(failed_run)
        await self._events.record_and_publish(
            project_id=failed_run.project_id,
            topic=EventTopic.RUN_FAILED,
            payload={
                "project_id": str(failed_run.project_id),
                "run_id": str(failed_run.id),
                "error": str(error),
            },
            created_at=failed_run.finished_at or self._now(),
        )
        return failed_run

    async def persist_run(self, run: Run) -> Run:
        async with self._unit_of_work() as unit_of_work:
            existing = await unit_of_work.runs.get(run.id)
            if existing is not None:
                persisted = await unit_of_work.runs.update(run)
            else:
                persisted = await unit_of_work.runs.add(run)
            await unit_of_work.commit()
            return persisted

    async def _record_child_node_created(
        self,
        *,
        succeeded_run: Run,
        child_node: Node,
        child_code_snapshot: CodeSnapshot,
        child_context_snapshot: ContextSnapshot,
        committed_sha: str,
        git_ref: str,
        child_created_at: datetime,
    ) -> None:
        await self._events.record_and_publish(
            project_id=succeeded_run.project_id,
            topic=(
                EventTopic.RESOLUTION_NODE_CREATED
                if child_node.kind is NodeKind.RESOLUTION
                else EventTopic.PROMPT_NODE_CREATED
            ),
            payload={
                "project_id": str(succeeded_run.project_id),
                "run_id": str(succeeded_run.id),
                "node_id": str(child_node.id),
                "parent_node_ids": [str(parent_id) for parent_id in child_node.parent_node_ids],
                "code_snapshot_id": str(child_code_snapshot.id),
                "context_snapshot_id": str(child_context_snapshot.id),
                "commit_sha": committed_sha,
                "git_ref": git_ref,
                "title": child_node.title,
            },
            created_at=child_created_at,
        )
