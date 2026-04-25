from __future__ import annotations

from fastapi import APIRouter, Depends

from agentsofchaos_orchestrator.api.dependencies import get_settings
from agentsofchaos_orchestrator.api.schemas import HealthResponse
from agentsofchaos_orchestrator.infrastructure.settings import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)
