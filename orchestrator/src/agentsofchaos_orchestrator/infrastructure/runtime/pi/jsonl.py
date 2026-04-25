from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

from agentsofchaos_orchestrator.domain.errors import RuntimeExecutionError
from agentsofchaos_orchestrator.infrastructure.runtime.pi.events import JsonObject


async def iter_jsonl_lines(reader: asyncio.StreamReader) -> AsyncIterator[str]:
    buffer = bytearray()
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        buffer.extend(chunk)
        while True:
            newline_index = buffer.find(b"\n")
            if newline_index == -1:
                break
            raw_line = bytes(buffer[:newline_index])
            del buffer[: newline_index + 1]
            yield decode_jsonl_line(raw_line)
    if buffer:
        yield decode_jsonl_line(bytes(buffer))


def decode_jsonl_line(raw_line: bytes) -> str:
    line = raw_line.decode("utf-8")
    if line.endswith("\r"):
        return line[:-1]
    return line


def parse_json_object(line: str, *, source: str) -> JsonObject:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as error:
        raise RuntimeExecutionError(f"Failed to parse {source} JSONL output: {error}") from error
    if not isinstance(parsed, dict):
        raise RuntimeExecutionError(f"Expected {source} JSON object: {type(parsed)!r}")
    return {str(key): cast(object, value) for key, value in parsed.items()}
