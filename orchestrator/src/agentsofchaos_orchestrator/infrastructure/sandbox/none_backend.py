from __future__ import annotations

import asyncio

from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    SandboxBackend,
    SandboxedExecutionRequest,
    SandboxedProcess,
    SandboxKind,
)


class NoSandboxBackend:
    """Spawns directly, no isolation.

    The default for local development and the only backend usable on
    hosts without bwrap/docker. Functionally equivalent to the
    pre-sandbox behaviour and chosen so that introducing the sandbox
    layer is a non-breaking refactor.
    """

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.NONE

    async def probe(self) -> None:
        return None

    async def spawn(self, request: SandboxedExecutionRequest) -> SandboxedProcess:
        spec = request.spec
        process = await asyncio.create_subprocess_exec(
            *spec.command,
            cwd=str(spec.cwd),
            env=dict(spec.env),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return process  # type: ignore[return-value]


# Static-typing assertion so the protocol stays in sync with this impl.
_: SandboxBackend = NoSandboxBackend()
