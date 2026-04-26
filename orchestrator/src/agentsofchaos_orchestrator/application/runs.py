from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.artifacts import ArtifactRecorder
from agentsofchaos_orchestrator.application.context_projection import (
    ContextEdit,
    ContextProjectionService,
    ContextResolutionRecord,
)
from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.application.run_state import RunStateService
from agentsofchaos_orchestrator.application.supervisor import RunSupervisor
from agentsofchaos_orchestrator.domain.enums import (
    ArtifactKind,
    NodeKind,
    NodeStatus,
    RuntimeKind,
    SandboxKind,
)
from agentsofchaos_orchestrator.domain.errors import (
    MergeAncestorError,
    MergeInvalidNodesError,
    NodeNotFoundError,
    ProjectNotFoundError,
    RuntimeCancelledError,
)
from agentsofchaos_orchestrator.domain.merge import (
    MergeReport,
    ResolutionContextDecisionReport,
    ResolutionReport,
)
from agentsofchaos_orchestrator.domain.models import (
    Artifact,
    CodeSnapshot,
    ContextSnapshot,
    Node,
    Project,
    Run,
)
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.runtime import (
    ContextItemEdit as RuntimeContextItemEdit,
)
from agentsofchaos_orchestrator.infrastructure.runtime import (
    ContextResolutionDecision as RuntimeContextResolutionDecision,
)
from agentsofchaos_orchestrator.infrastructure.runtime import (
    RuntimeAdapter,
    RuntimeCancellationToken,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


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
    child_kind: NodeKind = NodeKind.PROMPT
    child_parent_node_ids: tuple[UUID, ...] = ()
    original_user_prompt: str | None = None
    resolution_report_path: Path | None = None
    source_merge_report_artifact_id: UUID | None = None


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
        sandbox_kind: SandboxKind = SandboxKind.NONE,
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._settings = settings
        self._git_service = git_service
        self._runtime_adapter = runtime_adapter
        self._sandbox_kind = sandbox_kind
        self._artifact_recorder = artifact_recorder
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
        await self._start_prepared_run(prepared_run, title=None)
        return prepared_run.run

    async def run_merge_resolution_prompt(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        prompt: str,
        title: str | None = None,
    ) -> tuple[Run, Node]:
        prepared_run = await self._prepare_merge_resolution_run(
            project_id=project_id,
            merge_node_id=merge_node_id,
            user_prompt=prompt,
        )
        return await self._execute_prepared_prompt_run(prepared_run, title=title)

    async def start_merge_resolution_prompt_run(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        prompt: str,
    ) -> Run:
        prepared_run = await self._prepare_merge_resolution_run(
            project_id=project_id,
            merge_node_id=merge_node_id,
            user_prompt=prompt,
        )
        await self._start_prepared_run(prepared_run, title=None)
        return prepared_run.run

    async def _start_prepared_run(
        self,
        prepared_run: PreparedPromptRun,
        *,
        title: str | None,
    ) -> None:
        await self._supervisor.start(
            run_id=prepared_run.run.id,
            cancellation_token=prepared_run.cancellation_token,
            awaitable_factory=lambda: self._execute_prepared_prompt_run(
                prepared_run,
                title=title,
            ),
        )

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
            sandbox=self._sandbox_kind,
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
            child_parent_node_ids=(source_node.id,),
        )

    async def _prepare_merge_resolution_run(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        user_prompt: str,
    ) -> PreparedPromptRun:
        source_node, project, code_snapshot, context_snapshot = await self._load_run_source(
            merge_node_id
        )
        if project.id != project_id:
            raise NodeNotFoundError(
                f"Merge node {merge_node_id} does not belong to project {project_id}"
            )
        if source_node.kind is not NodeKind.MERGE:
            raise MergeInvalidNodesError(f"Node {merge_node_id} is not a merge node")
        if source_node.status not in {
            NodeStatus.CODE_CONFLICTED,
            NodeStatus.CONTEXT_CONFLICTED,
            NodeStatus.BOTH_CONFLICTED,
        }:
            raise MergeInvalidNodesError(f"Merge node {merge_node_id} is not conflicted")

        project_root = Path(project.root_path)
        report_path = self._merge_report_path(project_root, merge_node_id)
        if not report_path.is_file():
            raise MergeAncestorError(f"Merge report is missing for node {merge_node_id}")
        try:
            merge_report = MergeReport.model_validate_json(
                report_path.read_text(encoding="utf-8"),
            )
        except (OSError, ValidationError) as error:
            raise MergeAncestorError(
                f"Merge report is invalid for node {merge_node_id}"
            ) from error
        source_merge_report_artifact_id = await self._find_merge_report_artifact_id(
            project_id=project.id,
            merge_node_id=merge_node_id,
            report_path=report_path,
        )
        resolution_prompt = _resolution_prompt(
            user_prompt=user_prompt,
            merge_node=source_node,
            merge_report=merge_report,
        )

        run_id = self._new_uuid()
        child_node_id = self._new_uuid()
        runtime = self._runtime_adapter.runtime_kind
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        worktree_path = daemon_state_dir / "worktrees" / str(run_id)
        transcript_path = daemon_state_dir / "transcripts" / f"{run_id}.log"
        run = await self._run_state.create_queued_run(
            project=project,
            source_node=source_node,
            run_id=run_id,
            child_node_id=child_node_id,
            prompt=resolution_prompt,
            runtime=runtime,
            sandbox=self._sandbox_kind,
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
            child_kind=NodeKind.RESOLUTION,
            child_parent_node_ids=(source_node.id,),
            original_user_prompt=user_prompt,
            resolution_report_path=report_path,
            source_merge_report_artifact_id=source_merge_report_artifact_id,
        )

    async def _find_merge_report_artifact_id(
        self,
        *,
        project_id: UUID,
        merge_node_id: UUID,
        report_path: Path,
    ) -> UUID | None:
        async with self._unit_of_work() as unit_of_work:
            artifacts = await unit_of_work.artifacts.list_by_project(
                project_id,
                node_id=merge_node_id,
            )
        for artifact in artifacts:
            if artifact.kind is ArtifactKind.MERGE_REPORT and artifact.path == str(report_path):
                return artifact.id
        return None

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
        self._validate_resolution_if_needed(prepared_run)
        commit_message = (
            f"aoc resolution run {prepared_run.run.id}"
            if prepared_run.child_kind is NodeKind.RESOLUTION
            else f"aoc prompt run {prepared_run.run.id}"
        )
        committed_sha = self._git_service.commit_all(
            prepared_run.worktree_path,
            message=commit_message,
        )
        changed_files = self._git_service.changed_files_between(
            prepared_run.project_root,
            from_commit=prepared_run.code_snapshot.commit_sha,
            to_commit=committed_sha,
        )
        child_timestamp = self._now()
        context_edits = tuple(
            _to_context_edit(edit) for edit in runtime_result.context_edits
        )
        context_resolutions = tuple(
            _to_context_resolution(decision)
            for decision in runtime_result.context_resolutions
        )
        child_code_snapshot, child_context_snapshot = await self._create_child_snapshots(
            project=prepared_run.project,
            source_context=prepared_run.context_snapshot,
            child_node_id=prepared_run.child_node_id,
            run_id=prepared_run.run.id,
            prompt=prepared_run.original_user_prompt or prepared_run.run.prompt,
            summary_text=runtime_result.summary_text,
            transcript_path=prepared_run.transcript_path,
            committed_sha=committed_sha,
            changed_files=changed_files,
            created_at=child_timestamp,
            child_kind=prepared_run.child_kind,
            context_edits=context_edits,
            context_resolutions=context_resolutions,
            read_file_paths=runtime_result.read_file_paths,
        )
        child_node = await self._create_child_node(
            node_id=prepared_run.child_node_id,
            project=prepared_run.project,
            source_node=prepared_run.source_node,
            run_id=prepared_run.run.id,
            code_snapshot_id=child_code_snapshot.id,
            context_snapshot_id=child_context_snapshot.id,
            prompt=prepared_run.original_user_prompt or prepared_run.run.prompt,
            committed_sha=committed_sha,
            created_at=child_timestamp,
            title=title,
            child_kind=prepared_run.child_kind,
            parent_node_ids=prepared_run.child_parent_node_ids,
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
        runtime_artifacts = await self._artifact_recorder.record_run_artifacts(
            project_id=prepared_run.run.project_id,
            run_id=prepared_run.run.id,
            node_id=child_node.id,
            transcript_path=prepared_run.transcript_path,
            runtime_metadata=runtime_result.metadata,
            created_at=child_timestamp,
        )
        if prepared_run.child_kind is NodeKind.RESOLUTION:
            await self._record_resolution_report(
                prepared_run=prepared_run,
                child_node=child_node,
                committed_sha=committed_sha,
                git_ref=ref_name,
                changed_files=changed_files,
                runtime_metadata=runtime_result.metadata,
                runtime_artifacts=runtime_artifacts,
                context_resolutions=context_resolutions,
                created_at=child_timestamp,
            )
        succeeded_run = await self._run_state.succeed_run(
            running_run=prepared_run.run,
            child_node=child_node,
            child_code_snapshot=child_code_snapshot,
            child_context_snapshot=child_context_snapshot,
            committed_sha=committed_sha,
            git_ref=ref_name,
            child_created_at=child_timestamp,
            transcript_path=prepared_run.transcript_path,
            runtime_metadata=runtime_result.metadata,
            runtime_artifacts=runtime_artifacts,
        )
        return succeeded_run, child_node

    def _validate_resolution_if_needed(self, prepared_run: PreparedPromptRun) -> None:
        if prepared_run.child_kind is not NodeKind.RESOLUTION:
            return
        unmerged_files = self._git_service.unmerged_files(prepared_run.worktree_path)
        if unmerged_files:
            raise MergeAncestorError(
                "Resolution run left unmerged git index entries: "
                + ", ".join(unmerged_files)
            )
        marker_files = self._git_service.files_with_conflict_markers(
            prepared_run.worktree_path,
        )
        if marker_files:
            raise MergeAncestorError(
                "Resolution run left conflict markers in files: "
                + ", ".join(marker_files)
            )

    async def _record_resolution_report(
        self,
        *,
        prepared_run: PreparedPromptRun,
        child_node: Node,
        committed_sha: str,
        git_ref: str,
        changed_files: tuple[str, ...],
        runtime_metadata: dict[str, object],
        runtime_artifacts: tuple[Artifact, ...],
        context_resolutions: tuple[ContextResolutionRecord, ...],
        created_at: datetime,
    ) -> None:
        report_path = self._resolution_report_path(
            prepared_run.project_root,
            child_node.id,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_transcript_artifact = next(
            (
                artifact
                for artifact in runtime_artifacts
                if artifact.kind is ArtifactKind.RUNTIME_TRANSCRIPT
            ),
            None,
        )
        runtime_session_artifact_ids = tuple(
            artifact.id
            for artifact in runtime_artifacts
            if artifact.kind is ArtifactKind.RUNTIME_SESSION
        )
        report = ResolutionReport(
            conflicted_merge_node_id=prepared_run.source_node.id,
            successor_node_id=child_node.id,
            resolution_run_id=prepared_run.run.id,
            resolution_prompt=prepared_run.original_user_prompt or "",
            runtime_kind=prepared_run.runtime_kind,
            source_merge_report_path=(
                str(prepared_run.resolution_report_path)
                if prepared_run.resolution_report_path is not None
                else None
            ),
            source_merge_report_artifact_id=prepared_run.source_merge_report_artifact_id,
            runtime_transcript_artifact_id=(
                runtime_transcript_artifact.id
                if runtime_transcript_artifact is not None
                else None
            ),
            runtime_session_artifact_ids=runtime_session_artifact_ids,
            runtime_artifact_ids=tuple(artifact.id for artifact in runtime_artifacts),
            commit_sha=committed_sha,
            git_ref=git_ref,
            changed_files=changed_files,
            validated=True,
            runtime_metadata=runtime_metadata,
            context_resolutions=tuple(
                ResolutionContextDecisionReport(
                    section=decision.section,
                    item_id=decision.item_id,
                    chosen=decision.chosen,
                    text=decision.text,
                    rationale=decision.rationale,
                )
                for decision in context_resolutions
            ),
        )
        report_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        await self._artifact_recorder.record_artifact(
            project_id=prepared_run.project.id,
            kind=ArtifactKind.RESOLUTION_REPORT,
            path=report_path,
            media_type="application/json",
            artifact_metadata={"source": "resolution_run", "strategy": "agent-prompt-v0"},
            run_id=prepared_run.run.id,
            node_id=child_node.id,
            created_at=created_at,
        )

    def _merge_report_path(self, project_root: Path, merge_node_id: UUID) -> Path:
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        return daemon_state_dir / "artifacts" / f"merge-report-{merge_node_id}.json"

    def _resolution_report_path(self, project_root: Path, node_id: UUID) -> Path:
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        return daemon_state_dir / "artifacts" / f"resolution-report-{node_id}.json"

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
        child_kind: NodeKind,
        context_edits: tuple[ContextEdit, ...] = (),
        context_resolutions: tuple[ContextResolutionRecord, ...] = (),
        read_file_paths: tuple[str, ...] = (),
    ) -> tuple[CodeSnapshot, ContextSnapshot]:
        async with self._unit_of_work() as unit_of_work:
            code_snapshot = await unit_of_work.code_snapshots.add(
                project_id=project.id,
                commit_sha=committed_sha,
                git_ref=None,
            )
            if child_kind is NodeKind.RESOLUTION:
                child_context = self._context_projection.project_resolution_child_context(
                    project_id=project.id,
                    source_context=source_context,
                    child_node_id=child_node_id,
                    run_id=run_id,
                    prompt=prompt,
                    summary_text=summary_text,
                    transcript_path=transcript_path,
                    changed_files=changed_files,
                    created_at=created_at,
                    resolutions=context_resolutions,
                )
            else:
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
                    edits=context_edits,
                    read_file_paths=read_file_paths,
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
        child_kind: NodeKind,
        parent_node_ids: tuple[UUID, ...],
    ) -> Node:
        async with self._unit_of_work() as unit_of_work:
            node = await unit_of_work.nodes.add(
                node_id=node_id,
                project_id=project.id,
                kind=child_kind,
                parent_node_ids=parent_node_ids,
                code_snapshot_id=code_snapshot_id,
                context_snapshot_id=context_snapshot_id,
                status=NodeStatus.READY,
                title=title or _default_child_title(source_node, committed_sha, prompt),
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


def _to_context_edit(edit: RuntimeContextItemEdit) -> ContextEdit:
    return ContextEdit(section=edit.section, item_id=edit.item_id, text=edit.text)


def _to_context_resolution(
    decision: RuntimeContextResolutionDecision,
) -> ContextResolutionRecord:
    return ContextResolutionRecord(
        section=decision.section,
        item_id=decision.item_id,
        chosen=decision.chosen,
        text=decision.text,
        rationale=decision.rationale,
    )


def _default_child_title(source_node: Node, committed_sha: str, prompt: str) -> str:
    del source_node, committed_sha
    return _prompt_title(prompt)


def _prompt_title(prompt: str) -> str:
    single_line = " ".join(prompt.split())
    return single_line[:48] or "Prompt"


def _resolution_prompt(
    *,
    user_prompt: str,
    merge_node: Node,
    merge_report: MergeReport,
) -> str:
    report_text = json.dumps(
        merge_report.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    return "\n\n".join(
        (
            "You are resolving an Agents of Chaos conflicted merge node.",
            f"Conflicted merge node: {merge_node.id}",
            "Resolve the code and context conflicts in this worktree.",
            "Do not leave git conflict markers in files.",
            "Preserve provenance-worthy decisions in your final response.",
            "User resolution intent:",
            user_prompt,
            "Merge report JSON:",
            report_text,
        )
    )
