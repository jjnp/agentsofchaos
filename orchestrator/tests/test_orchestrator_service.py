from __future__ import annotations

from pathlib import Path

import pytest

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.enums import EventTopic, NodeKind, NodeStatus
from agentsofchaos_orchestrator.domain.errors import RootNodeAlreadyExistsError
from agentsofchaos_orchestrator.infrastructure.db import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.settings import Settings

from tests.helpers import initialize_test_repository, run_git


@pytest.mark.asyncio
async def test_open_project_is_idempotent(tmp_path: Path) -> None:
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
    )

    first = await service.open_project(repository_root)
    second = await service.open_project(repository_root)

    assert first.id == second.id
    assert Path(first.root_path) == repository_root.resolve()
    assert (repository_root / ".aoc").is_dir()

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_root_node_persists_graph_and_event(tmp_path: Path) -> None:
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
    )

    project = await service.open_project(repository_root)
    node = await service.create_root_node(project.id)
    graph = await service.get_graph(project.id)
    events = await service.list_events(project.id)

    assert node.kind is NodeKind.ROOT
    assert node.status is NodeStatus.READY
    assert graph.project.id == project.id
    assert len(graph.nodes) == 1
    assert graph.nodes[0].id == node.id
    assert events[-1].topic is EventTopic.ROOT_NODE_CREATED
    assert events[-1].payload["nodeId"] == str(node.id)

    root_ref = run_git(repository_root, "rev-parse", f"refs/aoc/nodes/{node.id}")
    head_ref = run_git(repository_root, "rev-parse", "HEAD")
    assert root_ref == head_ref

    await engine.dispose()


@pytest.mark.asyncio
async def test_second_root_node_is_rejected(tmp_path: Path) -> None:
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
    )

    project = await service.open_project(repository_root)
    await service.create_root_node(project.id)

    with pytest.raises(RootNodeAlreadyExistsError):
        await service.create_root_node(project.id)

    await engine.dispose()
