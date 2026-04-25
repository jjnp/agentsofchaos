from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol, TypeVar

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
_T = TypeVar("_T")


class AsyncStdin(Protocol):
    def write(self, data: bytes) -> None:
        ...

    async def drain(self) -> None:
        ...

    def close(self) -> None:
        ...

    def is_closing(self) -> bool:
        ...

    async def wait_closed(self) -> None:
        ...


class AsyncProcess(Protocol):
    stdin: AsyncStdin | None
    stdout: asyncio.StreamReader | None
    stderr: asyncio.StreamReader | None
    returncode: int | None

    def terminate(self) -> None:
        ...

    def kill(self) -> None:
        ...

    async def wait(self) -> int:
        ...


PiProcessFactory = Callable[[Path, tuple[str, ...], dict[str, str]], Awaitable[AsyncProcess]]


async def spawn_pi_process(
    cwd: Path,
    argv: tuple[str, ...],
    env: dict[str, str],
) -> AsyncProcess:
    return await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


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
