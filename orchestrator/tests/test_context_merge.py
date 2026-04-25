from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from agentsofchaos_orchestrator.application.context_merge import ContextMergeService
from agentsofchaos_orchestrator.domain.enums import ContextItemStatus
from agentsofchaos_orchestrator.domain.models import ContextItem, ContextSnapshot


def test_context_merge_marks_divergent_item_edits_as_conflicted() -> None:
    project_id = uuid4()
    ancestor_node_id = uuid4()
    item_id = uuid4()
    timestamp = datetime.now(UTC)
    ancestor_item = ContextItem(
        id=item_id,
        text="use sqlite",
        provenance_node_id=ancestor_node_id,
    )
    ancestor = ContextSnapshot(
        id=uuid4(),
        project_id=project_id,
        summary="ancestor",
        decisions=(ancestor_item,),
        created_at=timestamp,
    )
    source = ancestor.model_copy(
        update={
            "id": uuid4(),
            "decisions": (
                ancestor_item.model_copy(update={"text": "use sqlite with WAL"}),
            ),
        }
    )
    target = ancestor.model_copy(
        update={
            "id": uuid4(),
            "decisions": (
                ancestor_item.model_copy(update={"text": "use sqlite without WAL"}),
            ),
        }
    )
    service = ContextMergeService(new_uuid=uuid4)

    result = service.merge(
        project_id=project_id,
        ancestor=ancestor,
        source=source,
        target=target,
        merge_node_id=uuid4(),
        created_at=timestamp,
    )

    assert len(result.conflicts) == 1
    assert result.snapshot.decisions[0].status is ContextItemStatus.CONFLICTED
    assert result.snapshot.merge_metadata is not None
    assert result.snapshot.merge_metadata.conflicts == result.conflicts


def test_context_merge_accepts_one_sided_item_edit() -> None:
    project_id = uuid4()
    ancestor_node_id = uuid4()
    item_id = uuid4()
    timestamp = datetime.now(UTC)
    ancestor_item = ContextItem(
        id=item_id,
        text="ship locally first",
        provenance_node_id=ancestor_node_id,
    )
    ancestor = ContextSnapshot(
        id=uuid4(),
        project_id=project_id,
        summary="ancestor",
        goals=(ancestor_item,),
        created_at=timestamp,
    )
    source = ancestor.model_copy(
        update={
            "id": uuid4(),
            "goals": (
                ancestor_item.model_copy(update={"text": "ship local daemon first"}),
            ),
        }
    )
    target = ancestor.model_copy(update={"id": uuid4()})
    service = ContextMergeService(new_uuid=uuid4)

    result = service.merge(
        project_id=project_id,
        ancestor=ancestor,
        source=source,
        target=target,
        merge_node_id=uuid4(),
        created_at=timestamp,
    )

    assert result.conflicts == ()
    assert result.snapshot.goals[0].text == "ship local daemon first"
    assert result.snapshot.goals[0].status is ContextItemStatus.ACTIVE
