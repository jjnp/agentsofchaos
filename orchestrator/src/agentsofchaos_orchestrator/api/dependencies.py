from __future__ import annotations

from typing import cast

from fastapi import Request

from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.runtime.base import RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.sandbox.base import SandboxBackend
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_orchestrator_service(request: Request) -> OrchestratorService:
    return cast(OrchestratorService, request.app.state.orchestrator_service)


def get_event_bus(request: Request) -> InMemoryEventBus:
    return cast(InMemoryEventBus, request.app.state.event_bus)


def get_sandbox_backend(request: Request) -> SandboxBackend:
    return cast(SandboxBackend, request.app.state.sandbox_backend)


def get_runtime_adapter(request: Request) -> RuntimeAdapter:
    return cast(RuntimeAdapter, request.app.state.runtime_adapter)
