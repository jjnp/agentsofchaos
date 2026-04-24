from __future__ import annotations

from typing import cast

from agentsofchaos_orchestrator_v2.infrastructure.runtime.base import RuntimeEvent

JsonObject = dict[str, object]


def normalize_pi_event(payload: JsonObject) -> RuntimeEvent:
    payload_type = optional_str(payload.get("type")) or "unknown"
    message = None
    kind = f"pi.{payload_type}"
    durable = True

    if payload_type == "agent_start":
        kind = "runtime.agent_start"
        message = "Pi agent started processing the prompt."
    elif payload_type == "agent_end":
        kind = "runtime.agent_end"
        message = "Pi agent finished processing the prompt."
    elif payload_type == "turn_start":
        kind = "runtime.turn_start"
        message = "Pi started a new turn."
    elif payload_type == "turn_end":
        kind = "runtime.turn_end"
        message = "Pi completed a turn."
    elif payload_type == "message_start":
        kind = "runtime.message_start"
        message = _message_event_description(payload, default="Pi started a message.")
    elif payload_type == "message_update":
        delta = optional_object_dict(payload.get("assistantMessageEvent"))
        delta_type = optional_str(delta.get("type")) if delta is not None else None
        message = _message_update_text(delta)
        durable = delta_type not in {"text_delta", "thinking_delta", "toolcall_delta"}
        kind = "runtime.message_delta" if not durable else "runtime.message_update"
    elif payload_type == "message_end":
        kind = "runtime.message_end"
        message = _message_event_description(payload, default="Pi completed a message.")
    elif payload_type == "tool_execution_start":
        kind = "runtime.tool_execution_start"
        message = f"Pi started tool {optional_str(payload.get('toolName')) or 'unknown'}."
    elif payload_type == "tool_execution_update":
        kind = "runtime.tool_execution_update"
        message = _tool_partial_text(payload)
        durable = False
    elif payload_type == "tool_execution_end":
        kind = "runtime.tool_execution_end"
        message = f"Pi completed tool {optional_str(payload.get('toolName')) or 'unknown'}."
    elif payload_type == "queue_update":
        kind = "runtime.queue_update"
        message = "Pi updated the pending message queue."
    elif payload_type == "compaction_start":
        kind = "runtime.compaction_start"
        message = "Pi started compaction."
    elif payload_type == "compaction_end":
        kind = "runtime.compaction_end"
        message = "Pi finished compaction."
    elif payload_type == "auto_retry_start":
        kind = "runtime.auto_retry_start"
        message = "Pi started automatic retry handling."
    elif payload_type == "auto_retry_end":
        kind = "runtime.auto_retry_end"
        message = "Pi finished automatic retry handling."
    elif payload_type == "extension_error":
        kind = "runtime.extension_error"
        message = optional_str(payload.get("error")) or "Pi extension error."
    elif payload_type == "extension_ui_request":
        kind = "runtime.extension_ui_request"
        method = optional_str(payload.get("method")) or "unknown"
        message = f"Pi extension requested RPC UI method {method}."

    return RuntimeEvent(
        kind=kind,
        message=message,
        payload={"piEvent": payload, "piEventType": payload_type},
        durable=durable,
    )


def optional_object_dict(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    return {str(key): cast(object, item) for key, item in value.items()}


def optional_object_list(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    items: list[JsonObject] = []
    for item in value:
        if isinstance(item, dict):
            items.append({str(key): cast(object, subvalue) for key, subvalue in item.items()})
    return items


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _message_event_description(payload: JsonObject, *, default: str) -> str:
    message = optional_object_dict(payload.get("message"))
    role = optional_str(message.get("role")) if message is not None else None
    if role is None:
        return default
    return f"Pi {role} message event."


def _message_update_text(delta: JsonObject | None) -> str | None:
    if delta is None:
        return None
    delta_type = optional_str(delta.get("type"))
    if delta_type in {"text_delta", "thinking_delta", "toolcall_delta"}:
        return optional_str(delta.get("delta"))
    if delta_type == "done":
        return "Pi finished streaming a message."
    if delta_type == "error":
        return optional_str(delta.get("errorMessage")) or "Pi reported a message error."
    return None


def _tool_partial_text(payload: JsonObject) -> str | None:
    partial_result = optional_object_dict(payload.get("partialResult"))
    if partial_result is None:
        return None
    return extract_text_content(partial_result.get("content"))


def extract_text_content(content: object) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if not isinstance(content, list):
        return None
    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = optional_str(block.get("type"))
        if block_type == "text":
            text = optional_str(block.get("text"))
            if text is not None:
                text_parts.append(text)
    joined = "".join(text_parts).strip()
    return joined or None
