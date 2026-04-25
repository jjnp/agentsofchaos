from __future__ import annotations

from agentsofchaos_orchestrator.domain.enums import RuntimeKind
from agentsofchaos_orchestrator.infrastructure.runtime.base import RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.runtime.noop import NoOpRuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.runtime.pi.adapter import PiRuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.sandbox import (
    SandboxBackend,
    build_sandbox_backend,
)
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def build_runtime_adapter(
    settings: Settings,
    sandbox: SandboxBackend | None = None,
) -> RuntimeAdapter:
    """Build the runtime adapter the daemon should use.

    The sandbox is injected so the same Pi adapter can run with no
    isolation locally and under bubblewrap/docker in production. If
    omitted we resolve it from settings — convenient for callers that
    don't already hold a backend instance.
    """
    resolved_sandbox = sandbox if sandbox is not None else build_sandbox_backend(settings)
    if settings.runtime_backend is RuntimeKind.NOOP:
        return NoOpRuntimeAdapter()
    if settings.runtime_backend is RuntimeKind.PI:
        return PiRuntimeAdapter(
            pi_binary=settings.pi_binary,
            model=settings.pi_model,
            sandbox=resolved_sandbox,
        )
    raise ValueError(
        f"No runtime adapter ships for backend: {settings.runtime_backend.value}"
    )
