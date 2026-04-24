from __future__ import annotations

from pathlib import Path

import pytest

from agentsofchaos_orchestrator_v2.application.services import OrchestratorService
from agentsofchaos_orchestrator_v2.domain.enums import (
    EventTopic,
    NodeKind,
    RunStatus,
    RuntimeCapability,
    RuntimeKind,
)
from agentsofchaos_orchestrator_v2.infrastructure.db import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from agentsofchaos_orchestrator_v2.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator_v2.infrastructure.git_service import GitService
from agentsofchaos_orchestrator_v2.infrastructure.runtime import (
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from agentsofchaos_orchestrator_v2.infrastructure.settings import Settings
from tests.helpers import initialize_test_repository, run_git


class WritingRuntimeAdapter:
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
        target_path = request.worktree_path / "runtime-output.txt"
        target_path.write_text(f"prompt={request.prompt}\n", encoding="utf-8")
        await emit(
            RuntimeEvent(
                kind="runtime.file_written",
                message="Runtime wrote runtime-output.txt.",
                payload={"path": str(target_path.name)},
            )
        )
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: wrote runtime-output.txt\n",
            summary_text=f"Implemented prompt: {request.prompt}",
        )


@pytest.mark.asyncio
async def test_prompt_run_creates_child_node_commit_and_events(tmp_path: Path) -> None:
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
        runtime_adapter=WritingRuntimeAdapter(),
    )

    project = await service.open_project(repository_root)
    root_node = await service.create_root_node(project.id)
    run, child_node = await service.run_prompt(root_node.id, "add a runtime file")
    graph = await service.get_graph(project.id)
    events = await service.list_events(project.id)

    assert run.status is RunStatus.SUCCEEDED
    assert run.transcript_path is not None
    assert Path(run.transcript_path).is_file()
    assert child_node.kind is NodeKind.PROMPT
    assert child_node.parent_node_ids == (root_node.id,)
    assert len(graph.nodes) == 2

    child_ref_commit = run_git(repository_root, "rev-parse", f"refs/aoc/nodes/{child_node.id}")
    root_ref_commit = run_git(repository_root, "rev-parse", f"refs/aoc/nodes/{root_node.id}")
    assert child_ref_commit != root_ref_commit

    child_file_content = run_git(
        repository_root,
        "show",
        f"refs/aoc/nodes/{child_node.id}:runtime-output.txt",
    )
    assert child_file_content == "prompt=add a runtime file"

    topic_sequence = [event.topic for event in events]
    assert EventTopic.RUN_CREATED in topic_sequence
    assert EventTopic.RUN_STARTED in topic_sequence
    assert EventTopic.RUNTIME_EVENT in topic_sequence
    assert EventTopic.PROMPT_NODE_CREATED in topic_sequence
    assert EventTopic.ARTIFACT_CREATED in topic_sequence
    assert EventTopic.RUN_SUCCEEDED in topic_sequence

    runtime_events = [event for event in events if event.topic is EventTopic.RUNTIME_EVENT]
    assert len(runtime_events) == 1
    assert runtime_events[0].payload["runId"] == str(run.id)
    assert runtime_events[0].payload["runtimeKind"] == RuntimeKind.CUSTOM.value

    artifact_events = [event for event in events if event.topic is EventTopic.ARTIFACT_CREATED]
    assert len(artifact_events) == 1
    assert artifact_events[0].payload["kind"] == "runtime_transcript"
    assert artifact_events[0].payload["runId"] == str(run.id)

    daemon_state_dir = settings.daemon_state_dir_for_project(repository_root.resolve())
    worktree_path = daemon_state_dir / "worktrees" / str(run.id)
    assert not worktree_path.exists()

    await engine.dispose()
