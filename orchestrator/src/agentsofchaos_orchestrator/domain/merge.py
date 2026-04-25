from __future__ import annotations

from uuid import UUID

from pydantic import Field

from agentsofchaos_orchestrator.domain.enums import (
    CodeMergeSnapshotRole,
    ContextMergeSnapshotRole,
    MergeResolutionPolicy,
    NodeStatus,
)
from agentsofchaos_orchestrator.domain.models import ContextConflict, DomainModel


class CodeConflictStage(DomainModel):
    mode: str = Field(min_length=1)
    object_sha: str = Field(min_length=40, max_length=40)
    stage: str = Field(min_length=1)
    path: str = Field(min_length=1)


class CodeConflictFile(DomainModel):
    path: str = Field(min_length=1)
    marker_count: int = Field(ge=0)
    preview: str
    stages: tuple[CodeConflictStage, ...] = ()


class MergeSnapshotSemantics(DomainModel):
    code_snapshot_role: CodeMergeSnapshotRole
    context_snapshot_role: ContextMergeSnapshotRole
    resolution_policy: MergeResolutionPolicy
    node_status_is_immutable_outcome: bool = True


class CodeMergeReport(DomainModel):
    clean: bool
    snapshot_role: CodeMergeSnapshotRole
    contains_conflict_markers: bool
    resolution_required: bool
    conflicted_files: tuple[str, ...]
    conflict_details: tuple[CodeConflictFile, ...]
    changed_files: tuple[str, ...]
    stdout: str
    stderr: str


class ContextMergeReport(DomainModel):
    strategy_version: str = Field(min_length=1)
    snapshot_role: ContextMergeSnapshotRole
    resolution_required: bool
    conflict_count: int = Field(ge=0)
    conflicts: tuple[ContextConflict, ...] = ()


class MergeReport(DomainModel):
    merge_node_id: UUID
    status: NodeStatus
    source_node_id: UUID
    target_node_id: UUID
    ancestor_node_id: UUID
    source_code_snapshot_id: UUID
    target_code_snapshot_id: UUID
    ancestor_code_snapshot_id: UUID
    merged_code_snapshot_id: UUID
    source_context_snapshot_id: UUID
    target_context_snapshot_id: UUID
    ancestor_context_snapshot_id: UUID
    merged_context_snapshot_id: UUID
    commit_sha: str = Field(min_length=40, max_length=40)
    git_ref: str = Field(min_length=1)
    snapshot_semantics: MergeSnapshotSemantics
    code_merge: CodeMergeReport
    context_merge: ContextMergeReport
