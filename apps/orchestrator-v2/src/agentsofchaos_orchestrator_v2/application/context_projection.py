from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from agentsofchaos_orchestrator_v2.domain.models import (
    ContextItem,
    ContextSnapshot,
    FileReference,
)


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
    ) -> ContextSnapshot:
        return ContextSnapshot(
            id=self._new_uuid(),
            project_id=project_id,
            parent_ids=(source_context.id,),
            transcript_ref=str(transcript_path),
            summary=summary_text,
            goals=(
                *source_context.goals,
                ContextItem(
                    id=self._new_uuid(),
                    text=prompt,
                    provenance_node_id=child_node_id,
                    provenance_run_id=run_id,
                ),
            ),
            constraints=source_context.constraints,
            decisions=source_context.decisions,
            assumptions=source_context.assumptions,
            open_questions=source_context.open_questions,
            todos=source_context.todos,
            risks=source_context.risks,
            handoff_notes=(
                *source_context.handoff_notes,
                ContextItem(
                    id=self._new_uuid(),
                    text=f"Prompt run completed into node {child_node_id}.",
                    provenance_node_id=child_node_id,
                    provenance_run_id=run_id,
                ),
            ),
            read_files=source_context.read_files,
            touched_files=tuple(FileReference(path=path) for path in changed_files),
            symbols=source_context.symbols,
            created_at=created_at,
        )
