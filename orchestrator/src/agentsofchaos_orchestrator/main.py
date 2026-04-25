from __future__ import annotations

import uvicorn

from agentsofchaos_orchestrator.api.app import create_app
from agentsofchaos_orchestrator.infrastructure.settings import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
