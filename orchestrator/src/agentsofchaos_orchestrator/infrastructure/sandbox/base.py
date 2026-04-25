from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field

# SandboxKind lives in the domain layer so Run can carry it as a typed
# field; re-exported here so infrastructure callers keep their existing
# import path.
from agentsofchaos_orchestrator.domain.enums import SandboxKind

if TYPE_CHECKING:
    from agentsofchaos_orchestrator.infrastructure.runtime.base import (
        RuntimeCancellationToken,
    )


__all_kinds__ = (SandboxKind,)


class SandboxNetworkPolicy(StrEnum):
    FULL = "full"
    NONE = "none"


class SandboxModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class SandboxedExecutionSpec(SandboxModel):
    """Everything the sandbox needs to spawn a process.

    Backends translate this into their native command form (bwrap argv,
    docker run argv, …). Adapters do not see backend-specific knobs
    here — only the policy they declare.
    """

    command: tuple[str, ...] = Field(min_length=1)
    cwd: Path
    read_write_mounts: tuple[Path, ...] = ()
    read_only_mounts: tuple[Path, ...] = ()
    # We require explicit env passthrough — adapters whitelist what they
    # need (e.g. OPENAI_API_KEY) instead of inheriting the daemon's
    # environment wholesale, which would defeat the sandbox.
    env: dict[str, str] = Field(default_factory=dict)
    network: SandboxNetworkPolicy = SandboxNetworkPolicy.NONE
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class SandboxedExecutionRequest:
    """Spec + transient handles. Kept off the Pydantic model because
    cancellation tokens and stdin bytes don't survive serialisation.
    """

    spec: SandboxedExecutionSpec
    cancellation_token: "RuntimeCancellationToken | None" = None
    stdin: bytes | None = None


class AsyncStdin(Protocol):
    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...

    def close(self) -> None: ...

    def is_closing(self) -> bool: ...

    async def wait_closed(self) -> None: ...


class SandboxedProcess(Protocol):
    """Backend-agnostic process handle.

    Mirrors the subset of asyncio.subprocess.Process that the PI
    adapter (and any future stdin/stdout-streaming adapter) uses. This
    keeps adapters portable across sandbox backends.
    """

    stdin: AsyncStdin | None
    stdout: asyncio.StreamReader | None
    stderr: asyncio.StreamReader | None
    returncode: int | None

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    async def wait(self) -> int: ...


SandboxSpawn = Callable[[SandboxedExecutionRequest], Awaitable[SandboxedProcess]]


class SandboxBackend(Protocol):
    """A pluggable boundary between adapter-spawned processes and the host."""

    @property
    def kind(self) -> SandboxKind: ...

    async def probe(self) -> None:
        """Verify the backend is usable on this host.

        Raise SandboxUnavailableError with a human-readable message if
        the backend can't be used (binary missing, permissions, etc.).
        Called once at daemon startup; failure aborts startup so we
        don't silently fall back to an unsafe configuration.
        """
        ...

    async def spawn(self, request: SandboxedExecutionRequest) -> SandboxedProcess:
        """Spawn the requested process inside this sandbox."""
        ...
