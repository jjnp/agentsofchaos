from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from agentsofchaos_orchestrator.api.dependencies import get_settings
from agentsofchaos_orchestrator.api.schemas import HealthResponse
from agentsofchaos_orchestrator.infrastructure.settings import Settings

router = APIRouter(tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)
