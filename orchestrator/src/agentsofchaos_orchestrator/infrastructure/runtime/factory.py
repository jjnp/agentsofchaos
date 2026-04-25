from __future__ import annotations

from agentsofchaos_orchestrator.infrastructure.runtime.base import RuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.runtime.noop import NoOpRuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.runtime.pi.adapter import PiRuntimeAdapter
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def build_runtime_adapter(settings: Settings) -> RuntimeAdapter:
    if settings.runtime_backend == "noop":
        return NoOpRuntimeAdapter()
    if settings.runtime_backend == "pi":
        return PiRuntimeAdapter(
            pi_binary=settings.pi_binary,
            model=settings.pi_model,
        )
    raise ValueError(f"Unsupported runtime backend: {settings.runtime_backend}")
