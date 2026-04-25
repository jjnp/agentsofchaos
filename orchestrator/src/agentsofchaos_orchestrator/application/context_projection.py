from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from agentsofchaos_orchestrator.domain.enums import (
    ContextItemStatus,
    ContextResolutionChoice,
    ContextSection,
)
from agentsofchaos_orchestrator.domain.models import (
    ContextItem,
    ContextSnapshot,
    FileReference,
)


@dataclass(frozen=True)
class ContextEdit:
    """Application-layer mirror of runtime.base.ContextItemEdit.

    Decouples the projection service from runtime infrastructure types.
    """

    section: ContextSection
    item_id: UUID
    text: str


@dataclass(frozen=True)
class ContextResolutionRecord:
    """Application-layer mirror of runtime.base.ContextResolutionDecision.

    Records which side won for a given conflict and why. Used both to drive
    the projection (replace conflicted items with resolved text) and to
    persist provenance into the resolution-report artifact.
    """

    section: ContextSection
    item_id: UUID
    chosen: ContextResolutionChoice
    text: str
    rationale: str = ""


class ContextProjectionService:
    def __init__(self, *, new_uuid: Callable[[], UUID]) -> None:
        self._new_uuid = new_uuid

    def project_prompt_child_context(
        self,
        *,
        project_id: UUID,
        source_context: ContextSnapshot,
        child_node_id: UUID,
        run_id: UUID,
        prompt: str,
        summary_text: str,
        transcript_path: Path,
        changed_files: tuple[str, ...],
        created_at: datetime,
        edits: tuple[ContextEdit, ...] = (),
    ) -> ContextSnapshot:
        sections = self._inherit_sections(source_context)
        sections[ContextSection.GOALS] = (
            *sections[ContextSection.GOALS],
            ContextItem(
                id=self._new_uuid(),
                text=prompt,
                provenance_node_id=child_node_id,
                provenance_run_id=run_id,
            ),
        )
        sections[ContextSection.HANDOFF_NOTES] = (
            *sections[ContextSection.HANDOFF_NOTES],
            ContextItem(
                id=self._new_uuid(),
                text=f"Prompt run completed into node {child_node_id}.",
                provenance_node_id=child_node_id,
                provenance_run_id=run_id,
            ),
        )
        for edit in edits:
            sections[edit.section] = self._apply_edit(
                sections[edit.section],
                edit=edit,
                child_node_id=child_node_id,
                run_id=run_id,
            )
        return self._build_snapshot(
            project_id=project_id,
            source_context=source_context,
            sections=sections,
            transcript_path=transcript_path,
            summary_text=summary_text,
            changed_files=changed_files,
            created_at=created_at,
        )

    def project_resolution_child_context(
        self,
        *,
        project_id: UUID,
        source_context: ContextSnapshot,
        child_node_id: UUID,
        run_id: UUID,
        prompt: str,
        summary_text: str,
        transcript_path: Path,
        changed_files: tuple[str, ...],
        created_at: datetime,
        resolutions: tuple[ContextResolutionRecord, ...] = (),
    ) -> ContextSnapshot:
        sections = self._inherit_sections(source_context)
        sections[ContextSection.HANDOFF_NOTES] = (
            *sections[ContextSection.HANDOFF_NOTES],
            ContextItem(
                id=self._new_uuid(),
                text=f"Resolution run completed into node {child_node_id}.",
                provenance_node_id=child_node_id,
                provenance_run_id=run_id,
            ),
        )
        for resolution in resolutions:
            sections[resolution.section] = self._apply_resolution(
                sections[resolution.section],
                resolution=resolution,
                child_node_id=child_node_id,
                run_id=run_id,
            )
        return self._build_snapshot(
            project_id=project_id,
            source_context=source_context,
            sections=sections,
            transcript_path=transcript_path,
            summary_text=summary_text,
            changed_files=changed_files,
            created_at=created_at,
        )

    def _inherit_sections(
        self, source_context: ContextSnapshot
    ) -> dict[ContextSection, tuple[ContextItem, ...]]:
        return {
            ContextSection.GOALS: source_context.goals,
            ContextSection.CONSTRAINTS: source_context.constraints,
            ContextSection.DECISIONS: source_context.decisions,
            ContextSection.ASSUMPTIONS: source_context.assumptions,
            ContextSection.OPEN_QUESTIONS: source_context.open_questions,
            ContextSection.TODOS: source_context.todos,
            ContextSection.RISKS: source_context.risks,
            ContextSection.HANDOFF_NOTES: source_context.handoff_notes,
        }

    def _apply_edit(
        self,
        items: tuple[ContextItem, ...],
        *,
        edit: ContextEdit,
        child_node_id: UUID,
        run_id: UUID,
    ) -> tuple[ContextItem, ...]:
        for index, item in enumerate(items):
            if item.id == edit.item_id:
                replaced = item.model_copy(
                    update={
                        "text": edit.text,
                        "provenance_node_id": child_node_id,
                        "provenance_run_id": run_id,
                    }
                )
                return (*items[:index], replaced, *items[index + 1 :])
        return (
            *items,
            ContextItem(
                id=edit.item_id,
                text=edit.text,
                provenance_node_id=child_node_id,
                provenance_run_id=run_id,
            ),
        )

    def _apply_resolution(
        self,
        items: tuple[ContextItem, ...],
        *,
        resolution: ContextResolutionRecord,
        child_node_id: UUID,
        run_id: UUID,
    ) -> tuple[ContextItem, ...]:
        for index, item in enumerate(items):
            if item.id == resolution.item_id:
                resolved = item.model_copy(
                    update={
                        "text": resolution.text,
                        "status": ContextItemStatus.RESOLVED,
                        "provenance_node_id": child_node_id,
                        "provenance_run_id": run_id,
                    }
                )
                return (*items[:index], resolved, *items[index + 1 :])
        return (
            *items,
            ContextItem(
                id=resolution.item_id,
                text=resolution.text,
                status=ContextItemStatus.RESOLVED,
                provenance_node_id=child_node_id,
                provenance_run_id=run_id,
            ),
        )

    def _build_snapshot(
        self,
        *,
        project_id: UUID,
        source_context: ContextSnapshot,
        sections: dict[ContextSection, tuple[ContextItem, ...]],
        transcript_path: Path,
        summary_text: str,
        changed_files: tuple[str, ...],
        created_at: datetime,
    ) -> ContextSnapshot:
        return ContextSnapshot(
            id=self._new_uuid(),
            project_id=project_id,
            parent_ids=(source_context.id,),
            transcript_ref=str(transcript_path),
            summary=summary_text,
            goals=sections[ContextSection.GOALS],
            constraints=sections[ContextSection.CONSTRAINTS],
            decisions=sections[ContextSection.DECISIONS],
            assumptions=sections[ContextSection.ASSUMPTIONS],
            open_questions=sections[ContextSection.OPEN_QUESTIONS],
            todos=sections[ContextSection.TODOS],
            risks=sections[ContextSection.RISKS],
            handoff_notes=sections[ContextSection.HANDOFF_NOTES],
            read_files=source_context.read_files,
            touched_files=tuple(FileReference(path=path) for path in changed_files),
            symbols=source_context.symbols,
            created_at=created_at,
        )
