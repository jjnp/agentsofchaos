from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.artifacts import ArtifactRecorder
from agentsofchaos_orchestrator.application.context_merge import ContextMergeService
from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.domain.enums import (
    ArtifactKind,
    EventTopic,
    NodeKind,
    NodeStatus,
)
from agentsofchaos_orchestrator.domain.errors import (
    MergeAncestorError,
    NodeNotFoundError,
)
from agentsofchaos_orchestrator.domain.models import (
    CodeSnapshot,
    ContextSnapshot,
    Node,
    Project,
)
from agentsofchaos_orchestrator.infrastructure.git_service import GitMergeResult, GitService
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class MergeNodeResult:
    node: Node
    ancestor_node: Node
    code_conflicts: tuple[str, ...]
    context_conflicts: tuple[dict[str, object], ...]
    report_path: Path


@dataclass(frozen=True)
class MergeInputs:
    project: Project
    source_node: Node
    target_node: Node
    ancestor_node: Node
    source_code: CodeSnapshot
    target_code: CodeSnapshot
    ancestor_code: CodeSnapshot
    source_context: ContextSnapshot
    target_context: ContextSnapshot
    ancestor_context: ContextSnapshot


class MergeApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        git_service: GitService,
        artifact_recorder: ArtifactRecorder,
        events: ApplicationEventRecorder,
        now: Callable[[], datetime],
        new_uuid: Callable[[], UUID],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._settings = settings
        self._git_service = git_service
        self._artifact_recorder = artifact_recorder
        self._events = events
        self._now = now
        self._new_uuid = new_uuid
        self._context_merge = ContextMergeService(new_uuid=new_uuid)

    async def merge_nodes(
        self,
        *,
        project_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        title: str | None = None,
    ) -> MergeNodeResult:
        inputs = await self._load_inputs(project_id, source_node_id, target_node_id)
        merge_node_id = self._new_uuid()
        timestamp = self._now()
        project_root = Path(inputs.project.root_path)
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        worktree_path = daemon_state_dir / "worktrees" / f"merge-{merge_node_id}"
        report_path = self._merge_report_path(project_root, merge_node_id)

        self._verify_code_ancestor(inputs)
        context_result = self._context_merge.merge(
            project_id=project_id,
            ancestor=inputs.ancestor_context,
            source=inputs.source_context,
            target=inputs.target_context,
            merge_node_id=merge_node_id,
            created_at=timestamp,
        )
        try:
            merge_result = self._execute_code_merge(
                project_root=project_root,
                worktree_path=worktree_path,
                target_commit=inputs.target_code.commit_sha,
                source_commit=inputs.source_code.commit_sha,
                merge_node_id=merge_node_id,
            )
            node_status = _merge_status(
                code_conflicts=merge_result.conflicted_files,
                context_conflicts=context_result.conflicts,
            )
            committed_sha = self._git_service.commit_all(
                worktree_path,
                message=f"aoc merge node {merge_node_id}",
            )
            changed_files = self._git_service.changed_files_between(
                project_root,
                from_commit=inputs.ancestor_code.commit_sha,
                to_commit=committed_sha,
            )
            node, code_snapshot = await self._persist_merge_node(
                inputs=inputs,
                merge_node_id=merge_node_id,
                context_snapshot=context_result.snapshot,
                committed_sha=committed_sha,
                status=node_status,
                title=title,
                created_at=timestamp,
            )
            ref_name = f"{self._settings.node_ref_prefix}/{node.id}"
            self._git_service.ensure_node_ref(
                project_root,
                ref_name=ref_name,
                commit_sha=committed_sha,
            )
            code_snapshot = await self._update_code_snapshot_git_ref(
                code_snapshot.id,
                git_ref=ref_name,
            )
            report = _merge_report(
                inputs=inputs,
                node=node,
                code_snapshot=code_snapshot,
                context_snapshot=context_result.snapshot,
                committed_sha=committed_sha,
                git_ref=ref_name,
                merge_result=merge_result,
                context_conflicts=context_result.conflicts,
                changed_files=changed_files,
            )
            _write_json(report_path, report)
            artifact = await self._artifact_recorder.record_artifact(
                project_id=project_id,
                kind=ArtifactKind.MERGE_REPORT,
                path=report_path,
                media_type="application/json",
                artifact_metadata={"source": "merge_service", "strategy": "git+context-v0"},
                node_id=node.id,
                created_at=timestamp,
            )
            await self._events.record_and_publish(
                project_id=project_id,
                topic=EventTopic.MERGE_NODE_CREATED,
                payload={
                    "projectId": str(project_id),
                    "nodeId": str(node.id),
                    "sourceNodeId": str(inputs.source_node.id),
                    "targetNodeId": str(inputs.target_node.id),
                    "ancestorNodeId": str(inputs.ancestor_node.id),
                    "codeSnapshotId": str(code_snapshot.id),
                    "contextSnapshotId": str(context_result.snapshot.id),
                    "commitSha": committed_sha,
                    "gitRef": ref_name,
                    "status": node.status.value,
                    "codeConflicts": list(merge_result.conflicted_files),
                    "contextConflictCount": len(context_result.conflicts),
                    "mergeReportArtifactId": str(artifact.id) if artifact is not None else None,
                },
                created_at=timestamp,
            )
            return MergeNodeResult(
                node=node,
                ancestor_node=inputs.ancestor_node,
                code_conflicts=merge_result.conflicted_files,
                context_conflicts=context_result.conflicts,
                report_path=report_path,
            )
        finally:
            self._git_service.remove_worktree(project_root, worktree_path=worktree_path)

    async def get_merge_report(self, *, project_id: UUID, node_id: UUID) -> dict[str, object]:
        async with self._unit_of_work() as unit_of_work:
            project = await unit_of_work.projects.get(project_id)
            if project is None:
                raise MergeAncestorError(f"Unknown project: {project_id}")
            node = await unit_of_work.nodes.get(node_id)
            if node is None or node.project_id != project_id or node.kind is not NodeKind.MERGE:
                raise NodeNotFoundError(f"Unknown merge node: {node_id}")
        report_path = self._merge_report_path(Path(project.root_path), node_id)
        if not report_path.is_file():
            raise MergeAncestorError(f"Merge report is missing for node {node_id}")
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise MergeAncestorError(f"Merge report is invalid for node {node_id}")
        return loaded

    def _merge_report_path(self, project_root: Path, merge_node_id: UUID) -> Path:
        daemon_state_dir = self._settings.daemon_state_dir_for_project(project_root)
        return daemon_state_dir / "artifacts" / f"merge-report-{merge_node_id}.json"

    async def _load_inputs(
        self,
        project_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
    ) -> MergeInputs:
        async with self._unit_of_work() as unit_of_work:
            project = await unit_of_work.projects.get(project_id)
            if project is None:
                raise MergeAncestorError(f"Unknown project: {project_id}")
            nodes = await unit_of_work.nodes.list_by_project(project_id)
            nodes_by_id = {node.id: node for node in nodes}
            source_node = nodes_by_id.get(source_node_id)
            target_node = nodes_by_id.get(target_node_id)
            if source_node is None:
                raise NodeNotFoundError(f"Unknown source node: {source_node_id}")
            if target_node is None:
                raise NodeNotFoundError(f"Unknown target node: {target_node_id}")
            if source_node.id == target_node.id:
                raise MergeAncestorError("Cannot merge a node with itself")
            ancestor_node = _nearest_common_ancestor(source_node, target_node, nodes_by_id)
            source_code = await _require_code_snapshot(unit_of_work, source_node)
            target_code = await _require_code_snapshot(unit_of_work, target_node)
            ancestor_code = await _require_code_snapshot(unit_of_work, ancestor_node)
            source_context = await _require_context_snapshot(unit_of_work, source_node)
            target_context = await _require_context_snapshot(unit_of_work, target_node)
            ancestor_context = await _require_context_snapshot(unit_of_work, ancestor_node)
            context_snapshots = await unit_of_work.context_snapshots.list_by_project(project_id)
            _verify_context_ancestor(
                ancestor=ancestor_context,
                source=source_context,
                target=target_context,
                snapshots=context_snapshots,
            )
            return MergeInputs(
                project=project,
                source_node=source_node,
                target_node=target_node,
                ancestor_node=ancestor_node,
                source_code=source_code,
                target_code=target_code,
                ancestor_code=ancestor_code,
                source_context=source_context,
                target_context=target_context,
                ancestor_context=ancestor_context,
            )

    def _verify_code_ancestor(self, inputs: MergeInputs) -> None:
        merge_base = self._git_service.merge_base(
            Path(inputs.project.root_path),
            inputs.source_code.commit_sha,
            inputs.target_code.commit_sha,
        )
        if merge_base != inputs.ancestor_code.commit_sha:
            raise MergeAncestorError(
                "Graph ancestor is not the git merge base for source and target nodes: "
                f"graph={inputs.ancestor_code.commit_sha} git={merge_base}"
            )

    def _execute_code_merge(
        self,
        *,
        project_root: Path,
        worktree_path: Path,
        target_commit: str,
        source_commit: str,
        merge_node_id: UUID,
    ) -> GitMergeResult:
        self._git_service.create_detached_worktree(
            project_root,
            worktree_path=worktree_path,
            commit_sha=target_commit,
        )
        del merge_node_id
        return self._git_service.merge_no_commit(worktree_path, commit_sha=source_commit)

    async def _persist_merge_node(
        self,
        *,
        inputs: MergeInputs,
        merge_node_id: UUID,
        context_snapshot: ContextSnapshot,
        committed_sha: str,
        status: NodeStatus,
        title: str | None,
        created_at: datetime,
    ) -> tuple[Node, CodeSnapshot]:
        async with self._unit_of_work() as unit_of_work:
            code_snapshot = await unit_of_work.code_snapshots.add(
                project_id=inputs.project.id,
                commit_sha=committed_sha,
                git_ref=None,
            )
            persisted_context = await unit_of_work.context_snapshots.add(context_snapshot)
            node = await unit_of_work.nodes.add(
                project_id=inputs.project.id,
                kind=NodeKind.MERGE,
                parent_node_ids=(inputs.source_node.id, inputs.target_node.id),
                code_snapshot_id=code_snapshot.id,
                context_snapshot_id=persisted_context.id,
                status=status,
                title=title or _default_merge_title(inputs.source_node, inputs.target_node),
                created_at=created_at,
                node_id=merge_node_id,
            )
            await unit_of_work.commit()
            return node, code_snapshot

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


def _nearest_common_ancestor(
    source_node: Node,
    target_node: Node,
    nodes_by_id: dict[UUID, Node],
) -> Node:
    source_distances = _ancestor_distances(source_node, nodes_by_id)
    target_distances = _ancestor_distances(target_node, nodes_by_id)
    common_ids = set(source_distances).intersection(target_distances)
    if not common_ids:
        raise MergeAncestorError(
            f"No common ancestor for nodes {source_node.id} and {target_node.id}"
        )
    ancestor_id = min(
        common_ids,
        key=lambda node_id: (
            max(source_distances[node_id], target_distances[node_id]),
            source_distances[node_id] + target_distances[node_id],
            str(node_id),
        ),
    )
    return nodes_by_id[ancestor_id]


def _ancestor_distances(node: Node, nodes_by_id: dict[UUID, Node]) -> dict[UUID, int]:
    distances: dict[UUID, int] = {node.id: 0}
    frontier: list[tuple[Node, int]] = [(node, 0)]
    while frontier:
        current, distance = frontier.pop(0)
        for parent_id in current.parent_node_ids:
            parent = nodes_by_id.get(parent_id)
            if parent is None:
                continue
            next_distance = distance + 1
            existing = distances.get(parent.id)
            if existing is None or next_distance < existing:
                distances[parent.id] = next_distance
                frontier.append((parent, next_distance))
    return distances


async def _require_code_snapshot(unit_of_work: Any, node: Node) -> CodeSnapshot:
    snapshot = await unit_of_work.code_snapshots.get(node.code_snapshot_id)
    if snapshot is None:
        raise MergeAncestorError(f"Missing code snapshot for node {node.id}")
    return snapshot


async def _require_context_snapshot(unit_of_work: Any, node: Node) -> ContextSnapshot:
    snapshot = await unit_of_work.context_snapshots.get(node.context_snapshot_id)
    if snapshot is None:
        raise MergeAncestorError(f"Missing context snapshot for node {node.id}")
    return snapshot


def _verify_context_ancestor(
    *,
    ancestor: ContextSnapshot,
    source: ContextSnapshot,
    target: ContextSnapshot,
    snapshots: tuple[ContextSnapshot, ...],
) -> None:
    snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
    if not _context_snapshot_descends_from(source, ancestor.id, snapshots_by_id):
        raise MergeAncestorError(
            f"Source context snapshot {source.id} does not descend from {ancestor.id}"
        )
    if not _context_snapshot_descends_from(target, ancestor.id, snapshots_by_id):
        raise MergeAncestorError(
            f"Target context snapshot {target.id} does not descend from {ancestor.id}"
        )


def _context_snapshot_descends_from(
    snapshot: ContextSnapshot,
    ancestor_id: UUID,
    snapshots_by_id: dict[UUID, ContextSnapshot],
) -> bool:
    if snapshot.id == ancestor_id:
        return True
    frontier = list(snapshot.parent_ids)
    seen: set[UUID] = set()
    while frontier:
        current_id = frontier.pop(0)
        if current_id == ancestor_id:
            return True
        if current_id in seen:
            continue
        seen.add(current_id)
        current = snapshots_by_id.get(current_id)
        if current is not None:
            frontier.extend(current.parent_ids)
    return False


def _merge_status(
    *,
    code_conflicts: tuple[str, ...],
    context_conflicts: tuple[dict[str, object], ...],
) -> NodeStatus:
    has_code_conflicts = bool(code_conflicts)
    has_context_conflicts = bool(context_conflicts)
    if has_code_conflicts and has_context_conflicts:
        return NodeStatus.BOTH_CONFLICTED
    if has_code_conflicts:
        return NodeStatus.CODE_CONFLICTED
    if has_context_conflicts:
        return NodeStatus.CONTEXT_CONFLICTED
    return NodeStatus.READY


def _default_merge_title(source_node: Node, target_node: Node) -> str:
    return f"Merge {source_node.title} into {target_node.title}"


def _merge_report(
    *,
    inputs: MergeInputs,
    node: Node,
    code_snapshot: CodeSnapshot,
    context_snapshot: ContextSnapshot,
    committed_sha: str,
    git_ref: str,
    merge_result: GitMergeResult,
    context_conflicts: tuple[dict[str, object], ...],
    changed_files: tuple[str, ...],
) -> dict[str, object]:
    return {
        "mergeNodeId": str(node.id),
        "status": node.status.value,
        "sourceNodeId": str(inputs.source_node.id),
        "targetNodeId": str(inputs.target_node.id),
        "ancestorNodeId": str(inputs.ancestor_node.id),
        "sourceCodeSnapshotId": str(inputs.source_code.id),
        "targetCodeSnapshotId": str(inputs.target_code.id),
        "ancestorCodeSnapshotId": str(inputs.ancestor_code.id),
        "mergedCodeSnapshotId": str(code_snapshot.id),
        "sourceContextSnapshotId": str(inputs.source_context.id),
        "targetContextSnapshotId": str(inputs.target_context.id),
        "ancestorContextSnapshotId": str(inputs.ancestor_context.id),
        "mergedContextSnapshotId": str(context_snapshot.id),
        "commitSha": committed_sha,
        "gitRef": git_ref,
        "codeMerge": {
            "clean": merge_result.clean,
            "conflictedFiles": list(merge_result.conflicted_files),
            "conflictDetails": [
                {
                    "path": detail.path,
                    "markerCount": detail.marker_count,
                    "preview": detail.preview,
                    "stages": list(detail.stages),
                }
                for detail in merge_result.conflict_details
            ],
            "changedFiles": list(changed_files),
            "stdout": merge_result.stdout,
            "stderr": merge_result.stderr,
        },
        "contextMerge": {
            "strategyVersion": ContextMergeService.strategy_version,
            "conflictCount": len(context_conflicts),
            "conflicts": list(context_conflicts),
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
