from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentsofchaos_orchestrator.domain.enums import RuntimeKind
from agentsofchaos_orchestrator.infrastructure.sandbox.base import SandboxKind


def _xdg_state_home() -> Path:
    """Return the XDG state directory (env override or `~/.local/state`).

    The daemon DB lives here so that starting the orchestrator from different
    working directories doesn't silently produce different SQLite files.
    """
    env_value = os.environ.get("XDG_STATE_HOME")
    if env_value:
        return Path(env_value)
    return Path.home() / ".local" / "state"


def _default_database_url() -> str:
    db_path = _xdg_state_home() / "aoc-orchestrator" / "orchestrator.sqlite3"
    return f"sqlite+aiosqlite:///{db_path}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AOC_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Agents of Chaos Orchestrator"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = Field(default_factory=_default_database_url)
    log_level: str = "INFO"
    daemon_state_dir_name: str = ".aoc"
    node_ref_prefix: str = "refs/aoc/nodes"
    allow_existing_root_node: bool = False
    runtime_backend: RuntimeKind = RuntimeKind.NOOP
    pi_binary: str = "pi"
    pi_model: str | None = None
    event_stream_keepalive_seconds: float = Field(default=15.0, gt=0.0)

    # Sandbox layer (see docs/adrs/0010-pluggable-sandbox-layer.md). Default
    # is NONE so local dev keeps working without bwrap/docker installed.
    sandbox_backend: SandboxKind = SandboxKind.NONE
    sandbox_bwrap_binary: str = "bwrap"
    sandbox_docker_binary: str = "docker"
    # Default image is intentionally unopinionated — operators pick one
    # that contains the toolchain their chosen runtime needs.
    sandbox_docker_image: str = "debian:stable-slim"

    def daemon_state_dir_for_project(self, project_root: Path) -> Path:
        return project_root / self.daemon_state_dir_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
