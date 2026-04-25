from __future__ import annotations

import json
from collections.abc import Sequence

from agentsofchaos_orchestrator.infrastructure.runtime.pi.events import (
    JsonObject,
    extract_text_content,
    optional_str,
)


def build_transcript(*, prompt: str, messages: Sequence[JsonObject]) -> str:
    lines = [f"USER: {prompt}"]
    for message in messages:
        lines.extend(_format_transcript_lines(message))
    return "\n".join(lines).rstrip() + "\n"


def _format_transcript_lines(message: JsonObject) -> list[str]:
    role = optional_str(message.get("role"))
    if role == "assistant":
        return _format_assistant_message(message)
    if role == "toolResult":
        tool_name = optional_str(message.get("toolName")) or "unknown"
        text = extract_text_content(message.get("content")) or ""
        return [f"TOOL_RESULT[{tool_name}]: {text}".rstrip()]
    if role == "bashExecution":
        command = optional_str(message.get("command")) or ""
        output = optional_str(message.get("output")) or ""
        return [f"BASH: {command}", output] if output else [f"BASH: {command}"]
    if role == "custom":
        custom_type = optional_str(message.get("customType")) or "unknown"
        text = extract_text_content(message.get("content")) or ""
        return [f"CUSTOM[{custom_type}]: {text}".rstrip()]
    if role == "branchSummary":
        summary = optional_str(message.get("summary")) or ""
        return [f"BRANCH_SUMMARY: {summary}".rstrip()]
    if role == "compactionSummary":
        summary = optional_str(message.get("summary")) or ""
        return [f"COMPACTION_SUMMARY: {summary}".rstrip()]
    if role == "user":
        text = extract_text_content(message.get("content")) or ""
        return [f"USER: {text}".rstrip()]
    return [json.dumps(message, sort_keys=True)]


def _format_assistant_message(message: JsonObject) -> list[str]:
    lines: list[str] = []
    content = message.get("content")
    text = extract_text_content(content)
    if text is not None:
        lines.append(f"ASSISTANT: {text}")
    lines.extend(_extract_tool_call_lines(content))
    if not lines:
        lines.append("ASSISTANT:")
    return lines


def _extract_tool_call_lines(content: object) -> list[str]:
    if not isinstance(content, list):
        return []
    lines: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "toolCall":
            continue
        tool_name = optional_str(block.get("name")) or "unknown"
        arguments = block.get("arguments")
        lines.append(
            f"ASSISTANT_TOOL_CALL[{tool_name}]: {json.dumps(arguments, sort_keys=True)}"
        )
    return lines
