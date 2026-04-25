from __future__ import annotations

from agentsofchaos_orchestrator.infrastructure.sandbox.base import (
    SandboxBackend,
    SandboxKind,
)
from agentsofchaos_orchestrator.infrastructure.sandbox.none_backend import NoSandboxBackend
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def build_sandbox_backend(settings: Settings) -> SandboxBackend:
    """Resolve the configured sandbox backend.

    Defaults to ``NoSandboxBackend`` so a fresh checkout runs without
    extra setup. Production-ish profiles flip ``AOC_SANDBOX_BACKEND``
    to ``bubblewrap`` (Linux) or ``docker`` (any host with the daemon).
    """
    if settings.sandbox_backend is SandboxKind.NONE:
        return NoSandboxBackend()
    if settings.sandbox_backend is SandboxKind.BUBBLEWRAP:
        from agentsofchaos_orchestrator.infrastructure.sandbox.bubblewrap import (
            BubblewrapSandboxBackend,
        )

        return BubblewrapSandboxBackend(bwrap_binary=settings.sandbox_bwrap_binary)
    if settings.sandbox_backend is SandboxKind.DOCKER:
        from agentsofchaos_orchestrator.infrastructure.sandbox.docker import (
            DockerSandboxBackend,
        )

        return DockerSandboxBackend(
            docker_binary=settings.sandbox_docker_binary,
            image=settings.sandbox_docker_image,
        )
    raise ValueError(f"Unknown sandbox backend: {settings.sandbox_backend!r}")
