from __future__ import annotations

import json
from pathlib import Path

import pytest

from uuid import UUID, uuid4

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.enums import (
    CodeMergeSnapshotRole,
    ContextItemStatus,
    ContextMergeSnapshotRole,
    ContextResolutionChoice,
    ContextSection,
    EventTopic,
    MergeResolutionPolicy,
    NodeKind,
    NodeStatus,
    RuntimeCapability,
    RuntimeKind,
)
from agentsofchaos_orchestrator.infrastructure.db import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.runtime import (
    ContextItemEdit,
    ContextResolutionDecision,
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from tests.helpers import initialize_test_repository, run_git


def _require_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def _require_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return list(value)


class PromptContentRuntimeAdapter:
    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.CUSTOM

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        file_name, content = request.prompt.split(":", maxsplit=1)
        (request.worktree_path / file_name).write_text(content, encoding="utf-8")
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: wrote {file_name}\n",
            summary_text=f"Wrote {file_name}",
        )


class ConflictResolvingRuntimeAdapter(PromptContentRuntimeAdapter):
    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        assert "You are resolving an Agents of Chaos conflicted merge node." in request.prompt
        assert "Merge report JSON:" in request.prompt
        (request.worktree_path / "conflict.txt").write_text("resolved\n", encoding="utf-8")
        return RuntimeExecutionResult(
            transcript_text="USER: resolve\nASSISTANT: resolved conflict.txt\n",
            summary_text="Resolved conflict.txt",
        )


class ContextEditingRuntimeAdapter:
    """Test runtime that emits a single ContextItemEdit per execution.

    Lets the test drive divergent edits to a known item id from two siblings,
    which is the only way to produce a context_conflicted merge end-to-end.
    """

    def __init__(
        self,
        *,
        target_item_id: UUID,
        section: ContextSection,
        file_name: str,
    ) -> None:
        self._target_item_id = target_item_id
        self._section = section
        self._file_name = file_name

    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.CUSTOM

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        text = request.prompt
        (request.worktree_path / self._file_name).write_text(text + "\n", encoding="utf-8")
        return RuntimeExecutionResult(
            transcript_text=f"USER: {text}\nASSISTANT: edited {self._section.value}\n",
            summary_text=f"Edited {self._section.value}",
            context_edits=(
                ContextItemEdit(
                    section=self._section,
                    item_id=self._target_item_id,
                    text=text,
                ),
            ),
        )


class ContextResolvingRuntimeAdapter(PromptContentRuntimeAdapter):
    """Resolution runtime that picks one side of a known context conflict."""

    def __init__(
        self,
        *,
        target_item_id: UUID,
        section: ContextSection,
        chosen: ContextResolutionChoice,
        text: str,
        rationale: str,
    ) -> None:
        self._target_item_id = target_item_id
        self._section = section
        self._chosen = chosen
        self._text = text
        self._rationale = rationale

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        assert "You are resolving an Agents of Chaos conflicted merge node." in request.prompt
        # Make sure something committable lands in the worktree.
        (request.worktree_path / "resolution-note.txt").write_text(
            f"resolved {self._section.value}\n", encoding="utf-8"
        )
        return RuntimeExecutionResult(
            transcript_text="USER: resolve\nASSISTANT: resolved context conflict\n",
            summary_text="Resolved context conflict",
            context_resolutions=(
                ContextResolutionDecision(
                    section=self._section,
                    item_id=self._target_item_id,
                    chosen=self._chosen,
                    text=self._text,
                    rationale=self._rationale,
                ),
            ),
        )


class BranchWritingRuntimeAdapter:
    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.CUSTOM

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        del emit
        file_name = "source.txt" if "source" in request.prompt else "target.txt"
        (request.worktree_path / file_name).write_text(request.prompt, encoding="utf-8")
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: wrote {file_name}\n",
            summary_text=f"Wrote {file_name}",
        )


@pytest.mark.asyncio
async def test_merge_nodes_creates_integration_node_and_report(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    database_path = tmp_path / "orchestrator.db"

    settings = Settings(database_url=f"sqlite+aiosqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=BranchWritingRuntimeAdapter(),
    )

    project = await service.open_project(repository_root)
    root_node = await service.create_root_node(project.id)
    _source_run, source_node = await service.run_prompt(root_node.id, "source branch")
    _target_run, target_node = await service.run_prompt(root_node.id, "target branch")

    merge_result = await service.merge_nodes(
        project_id=project.id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
    )
    merge_node = merge_result.node
    events = await service.list_events(project.id)

    assert merge_node.kind is NodeKind.MERGE
    assert merge_node.status is NodeStatus.READY
    assert merge_node.parent_node_ids == (source_node.id, target_node.id)
    assert merge_result.code_conflicts == ()
    assert merge_result.context_conflicts == ()
    assert merge_result.code_snapshot_role is CodeMergeSnapshotRole.INTEGRATION
    assert merge_result.context_snapshot_role is ContextMergeSnapshotRole.MERGED_CONTEXT
    assert merge_result.resolution_policy is MergeResolutionPolicy.SUCCESSOR_NODE
    assert merge_result.report_path.is_file()

    source_content = run_git(
        repository_root,
        "show",
        f"refs/aoc/nodes/{merge_node.id}:source.txt",
    )
    target_content = run_git(
        repository_root,
        "show",
        f"refs/aoc/nodes/{merge_node.id}:target.txt",
    )
    assert source_content == "source branch"
    assert target_content == "target branch"
    assert EventTopic.MERGE_NODE_CREATED in [event.topic for event in events]

    await engine.dispose()


@pytest.mark.asyncio
async def test_code_conflicted_merge_records_conflict_details(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    database_path = tmp_path / "orchestrator.db"

    settings = Settings(database_url=f"sqlite+aiosqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=PromptContentRuntimeAdapter(),
    )

    project = await service.open_project(repository_root)
    root_node = await service.create_root_node(project.id)
    _source_run, source_node = await service.run_prompt(root_node.id, "conflict.txt:source")
    _target_run, target_node = await service.run_prompt(root_node.id, "conflict.txt:target")

    merge_result = await service.merge_nodes(
        project_id=project.id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
    )
    report = await service.get_merge_report(
        project_id=project.id,
        node_id=merge_result.node.id,
    )
    file_report = json.loads(merge_result.report_path.read_text(encoding="utf-8"))

    assert report == file_report
    assert merge_result.node.status is NodeStatus.CODE_CONFLICTED
    assert merge_result.code_snapshot_role is CodeMergeSnapshotRole.CONFLICTED_WORKSPACE
    assert merge_result.context_snapshot_role is ContextMergeSnapshotRole.MERGED_CONTEXT
    assert merge_result.resolution_policy is MergeResolutionPolicy.SUCCESSOR_NODE
    assert merge_result.code_conflicts == ("conflict.txt",)
    snapshot_semantics = _require_object(report["snapshot_semantics"])
    code_merge = _require_object(report["code_merge"])
    conflict_details = _require_list(code_merge["conflict_details"])
    first_conflict_detail = _require_object(conflict_details[0])

    assert snapshot_semantics["code_snapshot_role"] == "conflicted_workspace"
    assert snapshot_semantics["resolution_policy"] == "successor_node"
    assert code_merge["snapshot_role"] == "conflicted_workspace"
    assert code_merge["resolution_required"] is True
    assert code_merge["conflicted_files"] == ["conflict.txt"]
    assert isinstance(first_conflict_detail["marker_count"], int)
    assert first_conflict_detail["marker_count"] >= 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_driven_resolution_run_creates_successor_node(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    database_path = tmp_path / "orchestrator.db"

    settings = Settings(database_url=f"sqlite+aiosqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=PromptContentRuntimeAdapter(),
    )

    project = await service.open_project(repository_root)
    root_node = await service.create_root_node(project.id)
    _source_run, source_node = await service.run_prompt(root_node.id, "conflict.txt:source")
    _target_run, target_node = await service.run_prompt(root_node.id, "conflict.txt:target")
    merge_result = await service.merge_nodes(
        project_id=project.id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
    )

    resolving_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ConflictResolvingRuntimeAdapter(),
    )
    run, resolution_node = await resolving_service.run_merge_resolution_prompt(
        project_id=project.id,
        merge_node_id=merge_result.node.id,
        prompt="Resolve using the target behavior but remove conflict markers.",
    )
    events = await resolving_service.list_events(project.id)

    assert run.status.value == "succeeded"
    assert resolution_node.kind is NodeKind.RESOLUTION
    assert resolution_node.status is NodeStatus.READY
    assert resolution_node.parent_node_ids == (merge_result.node.id,)
    assert EventTopic.RESOLUTION_NODE_CREATED in [event.topic for event in events]

    resolved_content = run_git(
        repository_root,
        "show",
        f"refs/aoc/nodes/{resolution_node.id}:conflict.txt",
    )
    assert resolved_content == "resolved"

    daemon_state_dir = settings.daemon_state_dir_for_project(repository_root.resolve())
    report_path = daemon_state_dir / "artifacts" / f"resolution-report-{resolution_node.id}.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["conflicted_merge_node_id"] == str(merge_result.node.id)
    assert report["successor_node_id"] == str(resolution_node.id)
    assert report["resolution_run_id"] == str(run.id)
    assert report["validated"] is True

    await engine.dispose()


@pytest.mark.asyncio
async def test_context_conflicted_merge_via_divergent_item_edits(tmp_path: Path) -> None:
    """Two siblings each emit a divergent edit on the same context item id.

    The merge classifier should land on CONTEXT_CONFLICTED (no code conflicts:
    each branch writes its own file). This is the first end-to-end driver of
    a context-only conflict — until runtimes could declare ContextItemEdit,
    no public path produced one.
    """
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    database_path = tmp_path / "orchestrator.db"

    settings = Settings(database_url=f"sqlite+aiosqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    decision_id = uuid4()
    section = ContextSection.DECISIONS

    seed_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="seed.txt",
        ),
    )
    project = await seed_service.open_project(repository_root)
    root_node = await seed_service.create_root_node(project.id)
    _seed_run, seed_node = await seed_service.run_prompt(root_node.id, "use sqlite")

    source_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="branch-a.txt",
        ),
    )
    _source_run, source_node = await source_service.run_prompt(seed_node.id, "use sqlite with WAL")

    target_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="branch-b.txt",
        ),
    )
    _target_run, target_node = await target_service.run_prompt(
        seed_node.id, "use sqlite without WAL"
    )

    merge_result = await target_service.merge_nodes(
        project_id=project.id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
    )

    assert merge_result.node.status is NodeStatus.CONTEXT_CONFLICTED
    assert merge_result.code_conflicts == ()
    assert len(merge_result.context_conflicts) == 1
    conflict = merge_result.context_conflicts[0]
    assert conflict.section == section.value
    assert conflict.item_id == decision_id
    assert merge_result.code_snapshot_role is CodeMergeSnapshotRole.INTEGRATION
    assert (
        merge_result.context_snapshot_role
        is ContextMergeSnapshotRole.CONFLICTED_CONTEXT_CANDIDATE
    )
    assert merge_result.resolution_policy is MergeResolutionPolicy.SUCCESSOR_NODE

    report = json.loads(merge_result.report_path.read_text(encoding="utf-8"))
    snapshot_semantics = _require_object(report["snapshot_semantics"])
    assert snapshot_semantics["context_snapshot_role"] == "conflicted_context_candidate"
    context_merge = _require_object(report["context_merge"])
    assert context_merge["resolution_required"] is True
    assert context_merge["conflict_count"] == 1
    conflicts_in_report = _require_list(context_merge["conflicts"])
    assert len(conflicts_in_report) == 1
    first_report_conflict = _require_object(conflicts_in_report[0])
    assert first_report_conflict["section"] == section.value
    assert first_report_conflict["item_id"] == str(decision_id)

    await engine.dispose()


@pytest.mark.asyncio
async def test_resolution_records_context_decisions(tmp_path: Path) -> None:
    """Resolution runtime emits ContextResolutionDecision; report persists provenance."""
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    database_path = tmp_path / "orchestrator.db"

    settings = Settings(database_url=f"sqlite+aiosqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await initialize_database(engine)

    decision_id = uuid4()
    section = ContextSection.DECISIONS

    seed_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="seed.txt",
        ),
    )
    project = await seed_service.open_project(repository_root)
    root_node = await seed_service.create_root_node(project.id)
    _seed_run, seed_node = await seed_service.run_prompt(root_node.id, "ship locally first")

    source_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="branch-a.txt",
        ),
    )
    _src_run, source_node = await source_service.run_prompt(seed_node.id, "ship local daemon first")

    target_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextEditingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            file_name="branch-b.txt",
        ),
    )
    _tgt_run, target_node = await target_service.run_prompt(seed_node.id, "ship hosted control plane first")

    merge_result = await target_service.merge_nodes(
        project_id=project.id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
    )
    assert merge_result.node.status is NodeStatus.CONTEXT_CONFLICTED

    chosen_text = "ship local daemon first"
    rationale = "Selected source: matches the demo timeline."
    resolving_service = OrchestratorService(
        session_factory=session_factory,
        settings=settings,
        git_service=GitService(),
        event_bus=InMemoryEventBus(),
        runtime_adapter=ContextResolvingRuntimeAdapter(
            target_item_id=decision_id,
            section=section,
            chosen=ContextResolutionChoice.SOURCE,
            text=chosen_text,
            rationale=rationale,
        ),
    )
    run, resolution_node = await resolving_service.run_merge_resolution_prompt(
        project_id=project.id,
        merge_node_id=merge_result.node.id,
        prompt="Take the source decision; we already shipped that infra.",
    )
    assert run.status.value == "succeeded"
    assert resolution_node.kind is NodeKind.RESOLUTION

    daemon_state_dir = settings.daemon_state_dir_for_project(repository_root.resolve())
    report_path = daemon_state_dir / "artifacts" / f"resolution-report-{resolution_node.id}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    decisions = _require_list(report["context_resolutions"])
    assert len(decisions) == 1
    decision = _require_object(decisions[0])
    assert decision["section"] == section.value
    assert decision["item_id"] == str(decision_id)
    assert decision["chosen"] == ContextResolutionChoice.SOURCE.value
    assert decision["text"] == chosen_text
    assert decision["rationale"] == rationale

    resolved_snapshot = await resolving_service.get_context_snapshot(
        project_id=project.id,
        snapshot_id=resolution_node.context_snapshot_id,
    )
    resolved_decisions = [
        item for item in resolved_snapshot.decisions if item.id == decision_id
    ]
    assert len(resolved_decisions) == 1
    assert resolved_decisions[0].text == chosen_text
    assert resolved_decisions[0].status is ContextItemStatus.RESOLVED

    await engine.dispose()
