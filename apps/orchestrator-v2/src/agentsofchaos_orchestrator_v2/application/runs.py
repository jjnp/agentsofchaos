from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator_v2.application.artifacts import ArtifactRecorder
from agentsofchaos_orchestrator_v2.application.context_projection import ContextProjectionService
from agentsofchaos_orchestrator_v2.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator_v2.application.run_state import RunStateService
from agentsofchaos_orchestrator_v2.application.supervisor import RunSupervisor
from agentsofchaos_orchestrator_v2.domain.enums import NodeKind, NodeStatus, RuntimeKind
from agentsofchaos_orchestrator_v2.domain.errors import (
    NodeNotFoundError,
    ProjectNotFoundError,
    RuntimeCancelledError,
)
from agentsofchaos_orchestrator_v2.domain.models import (
    CodeSnapshot,
    ContextSnapshot,
    Node,
    Project,
    Run,
)
from agentsofchaos_orchestrator_v2.infrastructure.git_service import GitService
from agentsofchaos_orchestrator_v2.infrastructure.unit_of_work import UnitOfWorkFactory
from agentsofchaos_orchestrator_v2.infrastructure.runtime import (
    RuntimeAdapter,
    RuntimeCancellationToken,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator_v2.infrastructure.settings import Settings


@dataclass(frozen=True)
class PreparedPromptRun:
    source_node: Node
    project: Project
    code_snapshot: CodeSnapshot
    context_snapshot: ContextSnapshot
    run: Run
    child_node_id: UUID
    runtime_kind: RuntimeKind
    project_root: Path
    daemon_state_dir: Path
    worktree_path: Path
    transcript_path: Path
    cancellation_token: RuntimeCancellationToken


class RunApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        git_service: GitService,
        runtime_adapter: RuntimeAdapter,
        artifact_recorder: ArtifactRecorder,
        events: ApplicationEventRecorder,
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._settings = settings
        self._git_service = git_service
        self._runtime_adapter = runtime_adapter
        self._events = events
        self._supervisor = RunSupervisor()
        self._run_state = RunStateService(
            session_factory=session_factory,
            artifact_recorder=artifact_recorder,
            events=events,
            now=now,
        )
        self._context_projection = ContextProjectionService(new_uuid=new_uuid)
        self._now = now
        self._new_uuid = new_uuid

    async def run_prompt(
        self,
        node_id: UUID,
        prompt: str,
        title: str | None = None,
    ) -> tuple[Run, Node]:
        prepared_run = await self._prepare_prompt_run(node_id=node_id, prompt=prompt)
        return await self._execute_prepared_prompt_run(prepared_run, title=title)

    async def start_prompt_run(self, node_id: UUID, prompt: str) -> Run:
        prepared_run = await self._prepare_prompt_run(node_id=node_id, prompt=prompt)
        await self._supervisor.start(
            run_id=prepared_run.run.id,
            cancellation_token=prepared_run.cancellation_token,
            awaitable_factory=lambda: self._execute_prepared_prompt_run(
                prepared_run,
                title=None,
            ),
        )
        return prepared_run.run

    async def cancel_run(self, run_id: UUID) -> bool:
        return await self._supervisor.cancel(run_id)

    async def shutdown(self) -> None:
        await self._supervisor.shutdown()

    async def _prepare_prompt_run(self, *, node_id: UUID, prompt: str) -> PreparedPromptRun:
        source_node, project, code_snapshot, context_snapshot = await self._load_run_source(
            node_id
        )
        run_id = self._new_uuid()
        child_node_id = self._new_uuid()
        runtime = self._runtime_adapter.runtime_kind
        project_root = Path(project.root_path)
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        worktree_path = daemon_state_dir / "worktrees" / str(run_id)
        transcript_path = daemon_state_dir / "transcripts" / f"{run_id}.log"
        run = await self._run_state.create_queued_run(
            project=project,
            source_node=source_node,
            run_id=run_id,
            child_node_id=child_node_id,
            prompt=prompt,
            runtime=runtime,
            worktree_path=worktree_path,
            created_at=self._now(),
        )
        running_run = await self._run_state.start_run(
            run,
            worktree_path=worktree_path,
            started_at=self._now(),
        )
        return PreparedPromptRun(
            source_node=source_node,
            project=project,
            code_snapshot=code_snapshot,
            context_snapshot=context_snapshot,
            run=running_run,
            child_node_id=child_node_id,
            runtime_kind=runtime,
            project_root=project_root,
            daemon_state_dir=daemon_state_dir,
            worktree_path=worktree_path,
            transcript_path=transcript_path,
            cancellation_token=RuntimeCancellationToken(),
        )

    async def _execute_prepared_prompt_run(
        self,
        prepared_run: PreparedPromptRun,
        *,
        title: str | None,
    ) -> tuple[Run, Node]:
        worktree_created = False
        try:
            self._git_service.create_detached_worktree(
                prepared_run.project_root,
                worktree_path=prepared_run.worktree_path,
                commit_sha=prepared_run.code_snapshot.commit_sha,
            )
            worktree_created = True
            runtime_result = await self._runtime_adapter.execute(
                request=RuntimeExecutionRequest(
                    run_id=prepared_run.run.id,
                    planned_child_node_id=prepared_run.child_node_id,
                    prompt=prepared_run.run.prompt,
                    source_node=prepared_run.source_node,
                    source_context=prepared_run.context_snapshot,
                    worktree_path=prepared_run.worktree_path,
                    daemon_state_dir=prepared_run.daemon_state_dir,
                    cancellation_token=prepared_run.cancellation_token,
                ),
                emit=lambda event: self._events.emit_runtime_event(
                    project_id=prepared_run.project.id,
                    run_id=prepared_run.run.id,
                    runtime_kind=prepared_run.runtime_kind,
                    event=event,
                ),
            )
            return await self._finalize_successful_prompt_run(
                prepared_run=prepared_run,
                runtime_result=runtime_result,
                title=title,
            )
        except RuntimeCancelledError as error:
            transcript_path = None
            if error.transcript_text is not None:
                prepared_run.transcript_path.write_text(
                    error.transcript_text,
                    encoding="utf-8",
                )
                transcript_path = prepared_run.transcript_path
            await self._run_state.cancel_run(
                prepared_run.run,
                transcript_path=transcript_path,
                runtime_metadata=error.runtime_metadata,
            )
            raise
        except Exception as error:
            await self._run_state.fail_run(prepared_run.run, error=error)
            raise
        finally:
            if worktree_created:
                self._git_service.remove_worktree(
                    prepared_run.project_root,
                    worktree_path=prepared_run.worktree_path,
                )

    async def _finalize_successful_prompt_run(
        self,
        *,
        prepared_run: PreparedPromptRun,
        runtime_result: RuntimeExecutionResult,
        title: str | None,
    ) -> tuple[Run, Node]:
        prepared_run.transcript_path.write_text(
            runtime_result.transcript_text,
            encoding="utf-8",
        )
        committed_sha = self._git_service.commit_all(
            prepared_run.worktree_path,
            message=f"aoc prompt run {prepared_run.run.id}",
        )
        changed_files = self._git_service.changed_files_between(
            prepared_run.project_root,
            from_commit=prepared_run.code_snapshot.commit_sha,
            to_commit=committed_sha,
        )
        child_timestamp = self._now()
        child_code_snapshot, child_context_snapshot = await self._create_child_snapshots(
            project=prepared_run.project,
            source_context=prepared_run.context_snapshot,
            child_node_id=prepared_run.child_node_id,
            run_id=prepared_run.run.id,
            prompt=prepared_run.run.prompt,
            summary_text=runtime_result.summary_text,
            transcript_path=prepared_run.transcript_path,
            committed_sha=committed_sha,
            changed_files=changed_files,
            created_at=child_timestamp,
        )
        child_node = await self._create_child_node(
            node_id=prepared_run.child_node_id,
            project=prepared_run.project,
            source_node=prepared_run.source_node,
            run_id=prepared_run.run.id,
            code_snapshot_id=child_code_snapshot.id,
            context_snapshot_id=child_context_snapshot.id,
            prompt=prepared_run.run.prompt,
            committed_sha=committed_sha,
            created_at=child_timestamp,
            title=title,
        )
        ref_name = f"{self._settings.node_ref_prefix}/{child_node.id}"
        self._git_service.ensure_node_ref(
            prepared_run.project_root,
            ref_name=ref_name,
            commit_sha=committed_sha,
        )
        child_code_snapshot = await self._update_code_snapshot_git_ref(
            child_code_snapshot.id,
            git_ref=ref_name,
        )
        succeeded_run = await self._run_state.succeed_run(
            running_run=prepared_run.run,
            child_node=child_node,
            source_node=prepared_run.source_node,
            child_code_snapshot=child_code_snapshot,
            child_context_snapshot=child_context_snapshot,
            committed_sha=committed_sha,
            git_ref=ref_name,
            child_created_at=child_timestamp,
            transcript_path=prepared_run.transcript_path,
            runtime_metadata=runtime_result.metadata,
        )
        return succeeded_run, child_node

    async def _load_run_source(
        self,
        node_id: UUID,
    ) -> tuple[Node, Project, CodeSnapshot, ContextSnapshot]:
        async with self._unit_of_work() as unit_of_work:
            source_node = await unit_of_work.nodes.get(node_id)
            if source_node is None:
                raise NodeNotFoundError(f"Unknown node: {node_id}")
            project = await unit_of_work.projects.get(source_node.project_id)
            if project is None:
                raise ProjectNotFoundError(f"Unknown project: {source_node.project_id}")
            code_snapshot = await unit_of_work.code_snapshots.get(source_node.code_snapshot_id)
            if code_snapshot is None:
                raise ValueError(f"Missing code snapshot for node {source_node.id}")
            context_snapshot = await unit_of_work.context_snapshots.get(
                source_node.context_snapshot_id
            )
            if context_snapshot is None:
                raise ValueError(f"Missing context snapshot for node {source_node.id}")
            return source_node, project, code_snapshot, context_snapshot

    async def _create_child_snapshots(
        self,
        *,
        project: Project,
        source_context: ContextSnapshot,
        child_node_id: UUID,
        run_id: UUID,
        prompt: str,
        summary_text: str,
        transcript_path: Path,
        committed_sha: str,
        changed_files: tuple[str, ...],
        created_at: datetime,
    ) -> tuple[CodeSnapshot, ContextSnapshot]:
        async with self._unit_of_work() as unit_of_work:
            code_snapshot = await unit_of_work.code_snapshots.add(
                project_id=project.id,
                commit_sha=committed_sha,
                git_ref=None,
            )
            child_context = self._context_projection.project_prompt_child_context(
                project_id=project.id,
                source_context=source_context,
                child_node_id=child_node_id,
                run_id=run_id,
                prompt=prompt,
                summary_text=summary_text,
                transcript_path=transcript_path,
                changed_files=changed_files,
                created_at=created_at,
            )
            persisted_context = await unit_of_work.context_snapshots.add(child_context)
            await unit_of_work.commit()
            return code_snapshot, persisted_context

    async def _create_child_node(
        self,
        *,
        node_id: UUID,
        project: Project,
        source_node: Node,
        run_id: UUID,
        code_snapshot_id: UUID,
        context_snapshot_id: UUID,
        prompt: str,
        committed_sha: str,
        created_at: datetime,
        title: str | None,
    ) -> Node:
        async with self._unit_of_work() as unit_of_work:
            node = await unit_of_work.nodes.add(
                node_id=node_id,
                project_id=project.id,
                kind=NodeKind.PROMPT,
                parent_node_ids=(source_node.id,),
                code_snapshot_id=code_snapshot_id,
                context_snapshot_id=context_snapshot_id,
                status=NodeStatus.READY,
                title=title or f"Prompt @ {committed_sha[:12]} · {prompt[:32]}",
                created_at=created_at,
                originating_run_id=run_id,
            )
            await unit_of_work.commit()
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
