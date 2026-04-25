from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentsofchaos_orchestrator.domain.enums import (
    ArtifactKind,
    ContextItemStatus,
    EventTopic,
    NodeKind,
    NodeStatus,
    RunStatus,
    RuntimeKind,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ContextItem(DomainModel):
    id: UUID
    text: str = Field(min_length=1)
    status: ContextItemStatus = ContextItemStatus.ACTIVE
    provenance_node_id: UUID
    provenance_run_id: UUID | None = None
    citations: tuple[str, ...] = ()


class FileReference(DomainModel):
    path: str = Field(min_length=1)


class SymbolReference(DomainModel):
    name: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    kind: str = Field(min_length=1)


class MergeMetadata(DomainModel):
    ancestor_context_snapshot_id: UUID
    source_context_snapshot_id: UUID
    target_context_snapshot_id: UUID
    conflicts: tuple[dict[str, Any], ...] = ()
    strategy_version: str = Field(min_length=1)


class ContextSnapshot(DomainModel):
    id: UUID
    project_id: UUID
    parent_ids: tuple[UUID, ...] = ()
    transcript_ref: str | None = None
    summary: str = ""
    goals: tuple[ContextItem, ...] = ()
    constraints: tuple[ContextItem, ...] = ()
    decisions: tuple[ContextItem, ...] = ()
    assumptions: tuple[ContextItem, ...] = ()
    open_questions: tuple[ContextItem, ...] = ()
    todos: tuple[ContextItem, ...] = ()
    risks: tuple[ContextItem, ...] = ()
    handoff_notes: tuple[ContextItem, ...] = ()
    read_files: tuple[FileReference, ...] = ()
    touched_files: tuple[FileReference, ...] = ()
    symbols: tuple[SymbolReference, ...] = ()
    merge_metadata: MergeMetadata | None = None
    created_at: datetime


class CodeSnapshot(DomainModel):
    id: UUID
    project_id: UUID
    commit_sha: str = Field(min_length=40, max_length=40)
    git_ref: str | None = None
    created_at: datetime


class Project(DomainModel):
    id: UUID
    root_path: str = Field(min_length=1)
    git_dir: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime


class Node(DomainModel):
    id: UUID
    project_id: UUID
    kind: NodeKind
    parent_node_ids: tuple[UUID, ...] = ()
    code_snapshot_id: UUID
    context_snapshot_id: UUID
    status: NodeStatus
    title: str = Field(min_length=1)
    created_at: datetime
    originating_run_id: UUID | None = None


class Run(DomainModel):
    id: UUID
    project_id: UUID
    source_node_id: UUID
    prompt: str = Field(min_length=1)
    planned_child_node_id: UUID | None = None
    status: RunStatus
    runtime: RuntimeKind
    worktree_path: str | None = None
    transcript_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Artifact(DomainModel):
    id: UUID
    project_id: UUID
    run_id: UUID | None = None
    node_id: UUID | None = None
    kind: ArtifactKind
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    artifact_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EventRecord(DomainModel):
    id: UUID
    project_id: UUID
    topic: EventTopic
    payload: dict[str, Any]
    created_at: datetime


class GraphSnapshot(DomainModel):
    project: Project
    nodes: tuple[Node, ...]
