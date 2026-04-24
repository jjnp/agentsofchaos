from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AOC_V2_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Agents of Chaos Orchestrator v2"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./.aoc-orchestrator-v2.sqlite3"
    log_level: str = "INFO"
    daemon_state_dir_name: str = ".aoc"
    node_ref_prefix: str = "refs/aoc/nodes"
    allow_existing_root_node: bool = False
    runtime_backend: Literal["noop", "pi"] = "noop"
    pi_binary: str = "pi"
    pi_model: str | None = None
    event_stream_keepalive_seconds: float = Field(default=15.0, gt=0.0)

    def daemon_state_dir_for_project(self, project_root: Path) -> Path:
        return project_root / self.daemon_state_dir_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
