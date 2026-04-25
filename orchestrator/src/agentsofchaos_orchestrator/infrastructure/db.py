from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agentsofchaos_orchestrator.infrastructure.orm import Base
from agentsofchaos_orchestrator.infrastructure.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    _ensure_sqlite_parent_dir(settings.database_url)
    return create_async_engine(settings.database_url, future=True)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Create the parent directory for file-backed SQLite URLs.

    The default DB lives under XDG_STATE_HOME/aoc-orchestrator/, which may
    not exist on a fresh machine. SQLite refuses to open a database whose
    parent directory is missing, so we materialise it here.
    """
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    if not url.database or url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def initialize_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
