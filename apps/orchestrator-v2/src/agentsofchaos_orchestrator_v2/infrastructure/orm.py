from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    root_path: Mapped[str] = mapped_column(Text, unique=True)
    git_dir: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class CodeSnapshotRecord(Base):
    __tablename__ = "code_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    commit_sha: Mapped[str] = mapped_column(String(40), index=True)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContextSnapshotRecord(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    parent_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    transcript_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    constraints: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    open_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    todos: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    risks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    handoff_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    read_files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    touched_files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    symbols: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    merge_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NodeRecord(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    parent_node_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    code_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("code_snapshots.id", ondelete="RESTRICT")
    )
    context_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("context_snapshots.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    originating_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("nodes.id", ondelete="RESTRICT"),
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text)
    planned_child_node_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    runtime: Mapped[str] = mapped_column(String(32))
    worktree_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    node_id: Mapped[str | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), index=True)
    path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(128))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventRecordORM(Base):
    __tablename__ = "event_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutboxEventRecord(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_record_id: Mapped[str] = mapped_column(
        ForeignKey("event_records.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
