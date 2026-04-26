from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    AsyncStdin,
    SandboxedProcess,
)

# Re-exports kept for callers that still want the old aliases.
AsyncProcess = SandboxedProcess

__all__ = ["AsyncProcess", "AsyncStdin", "await_with_timeout"]


async def await_with_timeout[T](
    awaitable: Awaitable[T],
    *,
    timeout_seconds: float | None,
    description: str,
) -> T:
    try:
        if timeout_seconds is None:
            return await awaitable
        return await asyncio.wait_for(awaitable, timeout_seconds)
    except TimeoutError as error:
        raise RuntimeExecutionError(f"Timed out while {description}") from error
