from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError

JsonObject = dict[str, object]
_SESSION_REGISTRY_LOCKS: dict[Path, asyncio.Lock] = {}


async def load_node_session_path(registry_path: Path, *, node_id: UUID) -> str | None:
    async with _session_registry_lock(registry_path):
        return await asyncio.to_thread(
            _load_node_session_path_sync,
            registry_path,
            node_id,
        )


async def store_node_session_path(
    registry_path: Path,
    *,
    node_id: UUID,
    session_file: str,
) -> None:
    async with _session_registry_lock(registry_path):
        await asyncio.to_thread(
            _store_node_session_path_sync,
            registry_path,
            node_id,
            session_file,
        )


def _session_registry_lock(registry_path: Path) -> asyncio.Lock:
    lock_key = registry_path.resolve(strict=False)
    lock = _SESSION_REGISTRY_LOCKS.get(lock_key)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_REGISTRY_LOCKS[lock_key] = lock
    return lock


def _load_node_session_path_sync(registry_path: Path, node_id: UUID) -> str | None:
    registry = _read_session_registry(registry_path)
    value = registry.get(str(node_id))
    return value if isinstance(value, str) and value else None


def _store_node_session_path_sync(
    registry_path: Path,
    node_id: UUID,
    session_file: str,
) -> None:
    registry = _read_session_registry(registry_path)
    registry[str(node_id)] = session_file
    _write_session_registry(registry_path, registry)


def _read_session_registry(registry_path: Path) -> JsonObject:
    if not registry_path.is_file():
        return {}
    try:
        parsed = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeExecutionError(f"Invalid pi session registry: {registry_path}") from error
    if not isinstance(parsed, dict):
        raise RuntimeExecutionError(f"Pi session registry is not an object: {registry_path}")
    return {str(key): cast(object, value) for key, value in parsed.items()}


def _write_session_registry(registry_path: Path, registry: JsonObject) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = registry_path.with_name(f".{registry_path.name}.{uuid4()}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(registry, file, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(registry_path)
        _fsync_directory(registry_path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _fsync_directory(directory: Path) -> None:
    try:
        directory_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
