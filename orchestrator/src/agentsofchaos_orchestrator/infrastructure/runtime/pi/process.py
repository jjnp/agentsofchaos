from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    AsyncStdin,
    SandboxedProcess,
)

# Re-exports kept for callers that still want the old aliases.
AsyncProcess = SandboxedProcess

__all__ = ["AsyncProcess", "AsyncStdin", "await_with_timeout"]

_T = TypeVar("_T")


async def await_with_timeout(
    awaitable: Awaitable[_T],
    *,
    timeout_seconds: float | None,
    description: str,
) -> _T:
    try:
        if timeout_seconds is None:
            return await awaitable
        return await asyncio.wait_for(awaitable, timeout_seconds)
    except asyncio.TimeoutError as error:
        raise RuntimeExecutionError(f"Timed out while {description}") from error
