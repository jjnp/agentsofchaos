from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.queries import QueryService
from agentsofchaos_orchestrator.domain.enums import ContextSection
from agentsofchaos_orchestrator.domain.models import ContextItem, ContextSnapshot
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class ContextItemDiff:
    item_id: UUID
    change_type: str  # 'added' | 'removed' | 'changed'
    before: ContextItem | None
    after: ContextItem | None


@dataclass(frozen=True)
class ContextSectionDiff:
    section: ContextSection
    additions: int
    removals: int
    changes: int
    items: tuple[ContextItemDiff, ...]


@dataclass(frozen=True)
class ContextDiff:
    node_id: UUID
    base_snapshot_id: UUID | None
    head_snapshot_id: UUID
    sections: tuple[ContextSectionDiff, ...]


_SECTION_FIELDS: tuple[ContextSection, ...] = (
    ContextSection.GOALS,
    ContextSection.CONSTRAINTS,
    ContextSection.DECISIONS,
    ContextSection.ASSUMPTIONS,
    ContextSection.OPEN_QUESTIONS,
    ContextSection.TODOS,
    ContextSection.RISKS,
    ContextSection.HANDOFF_NOTES,
)


def _section_items(snapshot: ContextSnapshot, section: ContextSection) -> tuple[ContextItem, ...]:
    return tuple(getattr(snapshot, section.value))


def _diff_section(
    section: ContextSection,
    base: ContextSnapshot | None,
    head: ContextSnapshot,
) -> ContextSectionDiff:
    base_items = _section_items(base, section) if base is not None else ()
    head_items = _section_items(head, section)
    base_by_id = {item.id: item for item in base_items}

    seen: set[UUID] = set()
    diffs: list[ContextItemDiff] = []

    # Walk head first to preserve display order; then anything left in base
    # that wasn't in head is "removed".
    for item in head_items:
        seen.add(item.id)
        before = base_by_id.get(item.id)
        if before is None:
            diffs.append(
                ContextItemDiff(
                    item_id=item.id,
                    change_type="added",
                    before=None,
                    after=item,
                )
            )
            continue
        if before != item:
            diffs.append(
                ContextItemDiff(
                    item_id=item.id,
                    change_type="changed",
                    before=before,
                    after=item,
                )
            )
    for item in base_items:
        if item.id in seen:
            continue
        diffs.append(
            ContextItemDiff(
                item_id=item.id,
                change_type="removed",
                before=item,
                after=None,
            )
        )

    additions = sum(1 for diff in diffs if diff.change_type == "added")
    removals = sum(1 for diff in diffs if diff.change_type == "removed")
    changes = sum(1 for diff in diffs if diff.change_type == "changed")
    return ContextSectionDiff(
        section=section,
        additions=additions,
        removals=removals,
        changes=changes,
        items=tuple(diffs),
    )


class ContextDiffApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        queries: QueryService,
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._queries = queries

    async def get_node_context_diff(
        self,
        *,
        project_id: UUID,
        node_id: UUID,
    ) -> ContextDiff:
        node = await self._queries.get_node(project_id=project_id, node_id=node_id)

        async with self._unit_of_work() as unit_of_work:
            head_snapshot = await unit_of_work.context_snapshots.get(node.context_snapshot_id)
            if head_snapshot is None:
                raise ValueError(
                    f"Context snapshot {node.context_snapshot_id} missing for node {node_id}"
                )

            base_snapshot: ContextSnapshot | None = None
            if node.parent_node_ids:
                parent_id = node.parent_node_ids[-1]
                parent = await unit_of_work.nodes.get(parent_id)
                if parent is not None:
                    base_snapshot = await unit_of_work.context_snapshots.get(
                        parent.context_snapshot_id
                    )

        sections = tuple(
            _diff_section(section, base_snapshot, head_snapshot)
            for section in _SECTION_FIELDS
        )
        return ContextDiff(
            node_id=node_id,
            base_snapshot_id=base_snapshot.id if base_snapshot is not None else None,
            head_snapshot_id=head_snapshot.id,
            sections=sections,
        )
