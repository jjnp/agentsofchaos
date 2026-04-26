from __future__ import annotations

from uuid import UUID

from pydantic import Field

from agentsofchaos_orchestrator.domain.enums import (
    CodeMergeSnapshotRole,
    ContextMergeSnapshotRole,
    ContextResolutionChoice,
    ContextSection,
    MergeResolutionPolicy,
    NodeStatus,
    RuntimeKind,
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


class ResolutionContextDecisionReport(DomainModel):
    section: ContextSection
    item_id: UUID
    chosen: ContextResolutionChoice
    text: str = Field(min_length=1)
    rationale: str = ""


class ResolutionReport(DomainModel):
    conflicted_merge_node_id: UUID
    successor_node_id: UUID
    resolution_run_id: UUID
    resolution_prompt: str
    runtime_kind: RuntimeKind
    source_merge_report_path: str | None = None
    source_merge_report_artifact_id: UUID | None = None
    runtime_transcript_artifact_id: UUID | None = None
    runtime_session_artifact_ids: tuple[UUID, ...] = ()
    runtime_artifact_ids: tuple[UUID, ...] = ()
    commit_sha: str = Field(min_length=40, max_length=40)
    git_ref: str = Field(min_length=1)
    changed_files: tuple[str, ...] = ()
    validated: bool = True
    runtime_metadata: dict[str, object] = Field(default_factory=dict)
    context_resolutions: tuple[ResolutionContextDecisionReport, ...] = ()
