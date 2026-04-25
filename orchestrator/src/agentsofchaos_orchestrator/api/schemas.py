from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentsofchaos_orchestrator.domain.enums import (
    CodeMergeSnapshotRole,
    ContextItemStatus,
    ContextMergeSnapshotRole,
    EventTopic,
    MergeResolutionPolicy,
    NodeKind,
    NodeStatus,
    RunStatus,
    RuntimeKind,
    SandboxKind,
)
from agentsofchaos_orchestrator.domain.models import (
    CodeSnapshot,
    ContextSnapshot,
    EventRecord,
    GraphSnapshot,
    Node,
    Project,
    Run,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class OpenProjectRequest(ApiModel):
    path: str = Field(min_length=1)


class PromptRunRequest(ApiModel):
    prompt: str = Field(min_length=1)


class MergeNodesRequest(ApiModel):
    source_node_id: UUID
    target_node_id: UUID
    title: str | None = Field(default=None, min_length=1)


class ProjectResponse(ApiModel):
    id: UUID
    root_path: str
    git_dir: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectResponse":
        return cls.model_validate(project.model_dump())


class NodeResponse(ApiModel):
    id: UUID
    project_id: UUID
    kind: NodeKind
    parent_node_ids: tuple[UUID, ...]
    code_snapshot_id: UUID
    context_snapshot_id: UUID
    status: NodeStatus
    title: str
    created_at: datetime
    originating_run_id: UUID | None = None

    @classmethod
    def from_domain(cls, node: Node) -> "NodeResponse":
        return cls.model_validate(node.model_dump())


class GraphResponse(ApiModel):
    project: ProjectResponse
    nodes: tuple[NodeResponse, ...]

    @classmethod
    def from_domain(cls, graph: GraphSnapshot) -> "GraphResponse":
        return cls(
            project=ProjectResponse.from_domain(graph.project),
            nodes=tuple(NodeResponse.from_domain(node) for node in graph.nodes),
        )


class MergeResponse(ApiModel):
    node: NodeResponse
    ancestor_node_id: UUID
    code_conflicts: tuple[str, ...]
    context_conflicts: tuple[dict[str, object], ...]
    code_snapshot_role: CodeMergeSnapshotRole
    context_snapshot_role: ContextMergeSnapshotRole
    resolution_policy: MergeResolutionPolicy
    report_path: str


class MergeReportResponse(ApiModel):
    report: dict[str, object]


class RunResponse(ApiModel):
    id: UUID
    project_id: UUID
    source_node_id: UUID
    prompt: str
    planned_child_node_id: UUID | None = None
    status: RunStatus
    runtime: RuntimeKind
    sandbox: SandboxKind = SandboxKind.NONE
    worktree_path: str | None = None
    transcript_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_domain(cls, run: Run) -> "RunResponse":
        return cls.model_validate(run.model_dump())


class EventResponse(ApiModel):
    id: UUID
    project_id: UUID
    topic: EventTopic
    payload: dict[str, object]
    created_at: datetime

    @classmethod
    def from_domain(cls, event: EventRecord) -> "EventResponse":
        return cls.model_validate(event.model_dump())


class HealthResponse(ApiModel):
    status: str
    app_name: str


class CodeSnapshotResponse(ApiModel):
    id: UUID
    project_id: UUID
    commit_sha: str
    git_ref: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, snapshot: CodeSnapshot) -> "CodeSnapshotResponse":
        return cls.model_validate(snapshot.model_dump())


class ContextItemResponse(ApiModel):
    id: UUID
    text: str
    status: ContextItemStatus
    provenance_node_id: UUID
    provenance_run_id: UUID | None
    citations: tuple[str, ...]


class FileReferenceResponse(ApiModel):
    path: str


class SymbolReferenceResponse(ApiModel):
    name: str
    file_path: str
    kind: str


class ContextSnapshotResponse(ApiModel):
    id: UUID
    project_id: UUID
    parent_ids: tuple[UUID, ...]
    transcript_ref: str | None
    summary: str
    goals: tuple[ContextItemResponse, ...]
    constraints: tuple[ContextItemResponse, ...]
    decisions: tuple[ContextItemResponse, ...]
    assumptions: tuple[ContextItemResponse, ...]
    open_questions: tuple[ContextItemResponse, ...]
    todos: tuple[ContextItemResponse, ...]
    risks: tuple[ContextItemResponse, ...]
    handoff_notes: tuple[ContextItemResponse, ...]
    read_files: tuple[FileReferenceResponse, ...]
    touched_files: tuple[FileReferenceResponse, ...]
    symbols: tuple[SymbolReferenceResponse, ...]
    merge_metadata: dict[str, Any] | None
    created_at: datetime

    @classmethod
    def from_domain(cls, snapshot: ContextSnapshot) -> "ContextSnapshotResponse":
        return cls.model_validate(snapshot.model_dump())


class DiffLineResponse(ApiModel):
    type: str  # 'context' | 'add' | 'remove'
    content: str


class DiffHunkResponse(ApiModel):
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: tuple[DiffLineResponse, ...]


class FileDiffResponse(ApiModel):
    path: str
    old_path: str
    new_path: str
    change_type: str  # 'modified' | 'added' | 'deleted' | 'renamed'
    additions: int
    deletions: int
    hunks: tuple[DiffHunkResponse, ...]


class DiffTotalsResponse(ApiModel):
    files: int
    additions: int
    deletions: int


class NodeDiffResponse(ApiModel):
    node_id: UUID
    base_commit_sha: str | None
    head_commit_sha: str
    totals: DiffTotalsResponse
    files: tuple[FileDiffResponse, ...]


class ContextItemDiffResponse(ApiModel):
    item_id: UUID
    change_type: str  # 'added' | 'removed' | 'changed'
    before: ContextItemResponse | None
    after: ContextItemResponse | None


class ContextSectionDiffResponse(ApiModel):
    section: str
    additions: int
    removals: int
    changes: int
    items: tuple[ContextItemDiffResponse, ...]


class ContextDiffTotalsResponse(ApiModel):
    additions: int
    removals: int
    changes: int


class ContextDiffResponse(ApiModel):
    node_id: UUID
    base_snapshot_id: UUID | None
    head_snapshot_id: UUID
    totals: ContextDiffTotalsResponse
    sections: tuple[ContextSectionDiffResponse, ...]
