from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from agentsofchaos_orchestrator_v2.domain.enums import ContextItemStatus
from agentsofchaos_orchestrator_v2.domain.models import (
    ContextItem,
    ContextSnapshot,
    FileReference,
    MergeMetadata,
    SymbolReference,
)


@dataclass(frozen=True)
class ContextMergeResult:
    snapshot: ContextSnapshot
    conflicts: tuple[dict[str, object], ...]


class ContextMergeService:
    strategy_version = "aoc-context-merge-v0"

    def __init__(self, *, new_uuid: Callable[[], UUID]) -> None:
        self._new_uuid = new_uuid

    def merge(
        self,
        *,
        project_id: UUID,
        ancestor: ContextSnapshot,
        source: ContextSnapshot,
        target: ContextSnapshot,
        merge_node_id: UUID,
        created_at: datetime,
    ) -> ContextMergeResult:
        conflicts: list[dict[str, object]] = []
        goals = self._merge_items("goals", ancestor.goals, source.goals, target.goals, conflicts)
        constraints = self._merge_items(
            "constraints",
            ancestor.constraints,
            source.constraints,
            target.constraints,
            conflicts,
        )
        decisions = self._merge_items(
            "decisions",
            ancestor.decisions,
            source.decisions,
            target.decisions,
            conflicts,
        )
        assumptions = self._merge_items(
            "assumptions",
            ancestor.assumptions,
            source.assumptions,
            target.assumptions,
            conflicts,
        )
        open_questions = self._merge_items(
            "open_questions",
            ancestor.open_questions,
            source.open_questions,
            target.open_questions,
            conflicts,
        )
        todos = self._merge_items("todos", ancestor.todos, source.todos, target.todos, conflicts)
        risks = self._merge_items("risks", ancestor.risks, source.risks, target.risks, conflicts)
        handoff_notes = self._merge_items(
            "handoff_notes",
            ancestor.handoff_notes,
            source.handoff_notes,
            target.handoff_notes,
            conflicts,
        )
        metadata = MergeMetadata(
            ancestor_context_snapshot_id=ancestor.id,
            source_context_snapshot_id=source.id,
            target_context_snapshot_id=target.id,
            conflicts=tuple(conflicts),
            strategy_version=self.strategy_version,
        )
        snapshot = ContextSnapshot(
            id=self._new_uuid(),
            project_id=project_id,
            parent_ids=(source.id, target.id),
            summary=self._merge_summary(
                ancestor=ancestor,
                source=source,
                target=target,
                conflict_count=len(conflicts),
            ),
            goals=goals,
            constraints=constraints,
            decisions=decisions,
            assumptions=assumptions,
            open_questions=open_questions,
            todos=todos,
            risks=risks,
            handoff_notes=(
                *handoff_notes,
                ContextItem(
                    id=self._new_uuid(),
                    text=f"Merged source and target context into node {merge_node_id}.",
                    provenance_node_id=merge_node_id,
                ),
            ),
            read_files=self._merge_file_references(source.read_files, target.read_files),
            touched_files=self._merge_file_references(source.touched_files, target.touched_files),
            symbols=self._merge_symbol_references(source.symbols, target.symbols),
            merge_metadata=metadata,
            created_at=created_at,
        )
        return ContextMergeResult(snapshot=snapshot, conflicts=tuple(conflicts))

    def _merge_items(
        self,
        section: str,
        ancestor_items: tuple[ContextItem, ...],
        source_items: tuple[ContextItem, ...],
        target_items: tuple[ContextItem, ...],
        conflicts: list[dict[str, object]],
    ) -> tuple[ContextItem, ...]:
        ancestor_by_id = {item.id: item for item in ancestor_items}
        source_by_id = {item.id: item for item in source_items}
        target_by_id = {item.id: item for item in target_items}
        ordered_ids = self._ordered_item_ids(ancestor_items, target_items, source_items)
        merged: list[ContextItem] = []
        for item_id in ordered_ids:
            ancestor = ancestor_by_id.get(item_id)
            source = source_by_id.get(item_id)
            target = target_by_id.get(item_id)
            candidate = self._merge_item(section, ancestor, source, target, conflicts)
            if candidate is not None:
                merged.append(candidate)
        return tuple(merged)

    def _merge_item(
        self,
        section: str,
        ancestor: ContextItem | None,
        source: ContextItem | None,
        target: ContextItem | None,
        conflicts: list[dict[str, object]],
    ) -> ContextItem | None:
        if ancestor is None:
            if source is not None and target is not None and source != target:
                conflicts.append(self._item_conflict(section, source.id, source, target))
                return target.model_copy(update={"status": ContextItemStatus.CONFLICTED})
            return target or source
        source_changed = source is not None and source != ancestor
        target_changed = target is not None and target != ancestor
        if source is None and target is None:
            return None
        if source_changed and target_changed and source != target:
            chosen = target or source or ancestor
            conflicts.append(self._item_conflict(section, ancestor.id, source, target))
            return chosen.model_copy(update={"status": ContextItemStatus.CONFLICTED})
        if target_changed:
            return target
        if source_changed:
            return source
        return target or source or ancestor

    def _item_conflict(
        self,
        section: str,
        item_id: UUID,
        source: ContextItem | None,
        target: ContextItem | None,
    ) -> dict[str, object]:
        return {
            "kind": "context_item_conflict",
            "section": section,
            "itemId": str(item_id),
            "source": source.model_dump(mode="json") if source is not None else None,
            "target": target.model_dump(mode="json") if target is not None else None,
        }

    def _ordered_item_ids(
        self,
        *item_groups: tuple[ContextItem, ...],
    ) -> tuple[UUID, ...]:
        ordered: list[UUID] = []
        seen: set[UUID] = set()
        for items in item_groups:
            for item in items:
                if item.id not in seen:
                    ordered.append(item.id)
                    seen.add(item.id)
        return tuple(ordered)

    def _merge_summary(
        self,
        *,
        ancestor: ContextSnapshot,
        source: ContextSnapshot,
        target: ContextSnapshot,
        conflict_count: int,
    ) -> str:
        return "\n\n".join(
            (
                "Merged context snapshot.",
                f"Ancestor: {ancestor.id}",
                f"Source: {source.id}",
                f"Target: {target.id}",
                f"Context conflicts: {conflict_count}",
                "Source summary:",
                source.summary,
                "Target summary:",
                target.summary,
            )
        )

    def _merge_file_references(
        self,
        source: tuple[FileReference, ...],
        target: tuple[FileReference, ...],
    ) -> tuple[FileReference, ...]:
        paths = sorted({item.path for item in (*source, *target)})
        return tuple(FileReference(path=path) for path in paths)

    def _merge_symbol_references(
        self,
        source: tuple[SymbolReference, ...],
        target: tuple[SymbolReference, ...],
    ) -> tuple[SymbolReference, ...]:
        by_key = {(item.name, item.file_path, item.kind): item for item in (*target, *source)}
        return tuple(by_key[key] for key in sorted(by_key))
