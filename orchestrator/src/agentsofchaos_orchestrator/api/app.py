from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentsofchaos_orchestrator.api.routes.health import router as health_router
from agentsofchaos_orchestrator.api.routes.projects import router as projects_router
from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.errors import (
    GitOperationError,
    InvalidRepositoryError,
    MergeAncestorError,
    NodeNotFoundError,
    ProjectNotFoundError,
    RootNodeAlreadyExistsError,
    RunNotFoundError,
    RuntimeCancelledError,
    RuntimeExecutionError,
    SnapshotNotFoundError,
)
from agentsofchaos_orchestrator.infrastructure.db import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.runtime import RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.runtime.factory import build_runtime_adapter
from agentsofchaos_orchestrator.infrastructure.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(app_settings)
        session_factory = create_session_factory(engine)
        event_bus = InMemoryEventBus()
        git_service = GitService()
        runtime_adapter: RuntimeAdapter = build_runtime_adapter(app_settings)
        orchestrator_service = OrchestratorService(
            session_factory=session_factory,
            settings=app_settings,
            git_service=git_service,
            event_bus=event_bus,
            runtime_adapter=runtime_adapter,
        )

        await initialize_database(engine)
        await orchestrator_service.reconcile_startup()
        await orchestrator_service.start_background_workers()

        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.event_bus = event_bus
        app.state.git_service = git_service
        app.state.orchestrator_service = orchestrator_service

        try:
            yield
        finally:
            await orchestrator_service.shutdown()
            await engine.dispose()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(projects_router)

    @app.exception_handler(InvalidRepositoryError)
    async def handle_invalid_repository(
        _request: Request,
        error: InvalidRepositoryError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_REPOSITORY", "message": str(error)}},
        )

    @app.exception_handler(ProjectNotFoundError)
    async def handle_project_not_found(
        _request: Request,
        error: ProjectNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "PROJECT_NOT_FOUND", "message": str(error)}},
        )

    @app.exception_handler(NodeNotFoundError)
    async def handle_node_not_found(
        _request: Request,
        error: NodeNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NODE_NOT_FOUND", "message": str(error)}},
        )

    @app.exception_handler(SnapshotNotFoundError)
    async def handle_snapshot_not_found(
        _request: Request,
        error: SnapshotNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SNAPSHOT_NOT_FOUND", "message": str(error)}},
        )

    @app.exception_handler(RunNotFoundError)
    async def handle_run_not_found(
        _request: Request,
        error: RunNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "RUN_NOT_FOUND", "message": str(error)}},
        )

    @app.exception_handler(RootNodeAlreadyExistsError)
    async def handle_root_exists(
        _request: Request,
        error: RootNodeAlreadyExistsError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "ROOT_NODE_ALREADY_EXISTS", "message": str(error)}},
        )

    @app.exception_handler(MergeAncestorError)
    async def handle_merge_ancestor_error(
        _request: Request,
        error: MergeAncestorError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "MERGE_ANCESTOR_ERROR", "message": str(error)}},
        )

    @app.exception_handler(GitOperationError)
    async def handle_git_operation_error(
        _request: Request,
        error: GitOperationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "GIT_OPERATION_ERROR", "message": str(error)}},
        )

    @app.exception_handler(RuntimeCancelledError)
    async def handle_runtime_cancelled_error(
        _request: Request,
        error: RuntimeCancelledError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "RUNTIME_CANCELLED", "message": str(error)}},
        )

    @app.exception_handler(RuntimeExecutionError)
    async def handle_runtime_execution_error(
        _request: Request,
        error: RuntimeExecutionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "RUNTIME_EXECUTION_ERROR", "message": str(error)}},
        )

    return app
