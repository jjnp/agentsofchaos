from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.enums import (
    EventTopic,
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
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from tests.helpers import initialize_test_repository, run_git


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
    assert merge_result.code_conflicts == ("conflict.txt",)
    assert report["codeMerge"]["conflictedFiles"] == ["conflict.txt"]
    assert report["codeMerge"]["conflictDetails"][0]["markerCount"] >= 1

    await engine.dispose()
