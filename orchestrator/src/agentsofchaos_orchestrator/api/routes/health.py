from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from agentsofchaos_orchestrator.api.dependencies import (
    get_runtime_adapter,
    get_sandbox_backend,
    get_settings,
)
from agentsofchaos_orchestrator.api.schemas import (
    HealthDiagnosticResponse,
    HealthResponse,
)
from agentsofchaos_orchestrator.domain.errors import (
    RuntimeExecutionError,
    SandboxUnavailableError,
)
from agentsofchaos_orchestrator.infrastructure.runtime.base import RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.sandbox.base import SandboxBackend
from agentsofchaos_orchestrator.infrastructure.settings import Settings

router = APIRouter(tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]
SandboxDependency = Annotated[SandboxBackend, Depends(get_sandbox_backend)]
RuntimeDependency = Annotated[RuntimeAdapter, Depends(get_runtime_adapter)]


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)


@router.get("/health/sandbox", response_model=HealthDiagnosticResponse)
async def health_sandbox(sandbox: SandboxDependency) -> HealthDiagnosticResponse:
    """Operator diagnostic: is the configured sandbox backend usable?

    Probes the same host-side prerequisites the daemon checks at
    startup (bwrap binary + userns enabled, docker daemon reachable,
    etc.) but on every request — so when something rotates an admin
    cert or sysctl flips, this surfaces it without restarting the
    daemon.
    """
    try:
        await sandbox.probe()
    except SandboxUnavailableError as exc:
        return HealthDiagnosticResponse(
            name=sandbox.kind.value, status="unavailable", detail=str(exc)
        )
    return HealthDiagnosticResponse(name=sandbox.kind.value, status="ok")


@router.get("/health/runtime", response_model=HealthDiagnosticResponse)
async def health_runtime(runtime: RuntimeDependency) -> HealthDiagnosticResponse:
    """Operator diagnostic: is the configured runtime adapter usable?

    For pi: checks the binary is on PATH and `~/.pi/agent/{auth,settings}.json`
    are present. For noop: always returns ok. Future runtimes can layer
    in their own checks (token expiry for hosted backends, daemon
    reachability for IDE-side runtimes, etc.).
    """
    try:
        await runtime.probe()
    except RuntimeExecutionError as exc:
        return HealthDiagnosticResponse(
            name=runtime.runtime_kind.value, status="unavailable", detail=str(exc)
        )
    return HealthDiagnosticResponse(name=runtime.runtime_kind.value, status="ok")
