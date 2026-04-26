from __future__ import annotations

from pathlib import Path

import pytest

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.enums import EventTopic, NodeKind, NodeStatus
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
    assert events[-1].payload["node_id"] == str(node.id)

    root_ref = run_git(repository_root, "rev-parse", f"refs/aoc/nodes/{node.id}")
    head_ref = run_git(repository_root, "rev-parse", "HEAD")
    assert root_ref == head_ref

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_root_node_is_idempotent_after_auto_root(tmp_path: Path) -> None:
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
    graph = await service.get_graph(project.id)
    assert len(graph.nodes) == 1
    auto_root = graph.nodes[0]

    explicit_root = await service.create_root_node(project.id)

    assert explicit_root.id == auto_root.id
    assert len((await service.get_graph(project.id)).nodes) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_events_since_returns_strict_suffix(tmp_path: Path) -> None:
    """The SSE replay-on-reconnect path on the route layer leans on
    `list_events_since`: given an event id the client has already seen,
    return only the events that landed after it. The cursor itself is
    excluded from the result. An unknown cursor returns `None` so the
    route layer can fall back to a full replay rather than silently
    dropping the gap.
    """
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
    initial_events = await service.list_events(project.id)
    assert len(initial_events) == 2  # project_opened + root_node_created
    cursor = initial_events[0]

    # Resume from the first event — should yield only the second.
    suffix = await service.list_events_since(project.id, after_event_id=cursor.id)
    assert suffix is not None
    assert len(suffix) == 1
    assert suffix[0].id == initial_events[1].id

    # Resume from the latest known event — should yield zero events.
    tail = initial_events[-1]
    after_tail = await service.list_events_since(project.id, after_event_id=tail.id)
    assert after_tail is not None
    assert after_tail == ()

    # Bogus cursor — should return None so the route falls back to
    # full historical replay (avoids silent gaps when an operator
    # switches databases between reconnects).
    from uuid import uuid4

    missing = await service.list_events_since(project.id, after_event_id=uuid4())
    assert missing is None

    await engine.dispose()
