import os
from typing import Any

import anthropic


DEFAULT_MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic/v1/messages"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "MiniMax-M2.7"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TIMEOUT_SECONDS = 30


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for msg in messages:
        role = (msg.get("role") or "").strip()
        content = msg.get("content")
        if not role:
            continue

        if isinstance(content, str):
            normalized.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": content}],
                }
            )
            continue

        if isinstance(content, list):
            normalized.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    return normalized


def _extract_text(response_data: dict[str, Any]) -> str:
    parts = response_data.get("content") or []
    text_chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            text_chunks.append(part["text"])
    return "".join(text_chunks).strip()


def _extract_text_from_blocks(blocks: list[Any]) -> str:
    text_chunks: list[str] = []
    for block in blocks:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "")
            if isinstance(text, str):
                text_chunks.append(text)
    return "".join(text_chunks).strip()


def _extract_structured_from_blocks(blocks: list[Any], tool_name: str | None = None) -> dict[str, Any] | None:
    for block in blocks:
        block_type = getattr(block, "type", None)
        if block_type != "tool_use":
            continue
        if tool_name:
            current_name = getattr(block, "name", None)
            if current_name != tool_name:
                continue
        value = getattr(block, "input", None)
        if isinstance(value, dict):
            return value
    return None


def _build_structured_tool_payload(response_format: dict[str, Any]) -> tuple[dict[str, Any], str]:
    rf_type = (response_format.get("type") or "").strip()
    if rf_type != "json_schema":
        raise ValueError("response_format.type currently supports only 'json_schema'")

    raw = response_format.get("json_schema")
    if isinstance(raw, dict):
        schema_name = (raw.get("name") or response_format.get("name") or "structured_output").strip()
        schema = raw.get("schema")
        description = (raw.get("description") or response_format.get("description") or "Return structured output").strip()
    else:
        schema_name = (response_format.get("name") or "structured_output").strip()
        schema = response_format.get("schema")
        description = (response_format.get("description") or "Return structured output").strip()

    if not schema_name:
        schema_name = "structured_output"
    if not isinstance(schema, dict):
        raise ValueError("response_format.json_schema.schema (or response_format.schema) must be an object")

    tool = {
        "name": schema_name,
        "description": description,
        "input_schema": schema,
    }
    return tool, schema_name


def _read_timeout_seconds() -> int:
    raw = os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(5, int(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _normalize_base_url(raw_url: str) -> str:
    value = (raw_url or "").strip().rstrip("/")
    if value.endswith("/v1/messages"):
        return value[: -len("/v1/messages")]
    if value.endswith("/messages"):
        return value[: -len("/messages")]
    return value


def call_messages_api(
    *,
    model: str | None,
    max_tokens: int | None,
    system: str | None,
    messages: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = (os.getenv("LLM_API_KEY", "") or os.getenv("MINIMAX_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("LLM_API_KEY is not configured")

    base_url_raw = os.getenv("MINIMAX_API_BASE_URL", DEFAULT_MINIMAX_BASE_URL).strip() or DEFAULT_MINIMAX_BASE_URL
    base_url = _normalize_base_url(base_url_raw)
    anthropic_version = (
        os.getenv("MINIMAX_ANTHROPIC_VERSION", DEFAULT_ANTHROPIC_VERSION).strip() or DEFAULT_ANTHROPIC_VERSION
    )
    selected_model = (model or os.getenv("MINIMAX_MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
    selected_max_tokens = max_tokens or int(os.getenv("MINIMAX_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    timeout_seconds = _read_timeout_seconds()

    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise ValueError("messages must contain at least one valid message")

    payload: dict[str, Any] = {
        "model": selected_model,
        "max_tokens": selected_max_tokens,
        "messages": normalized_messages,
    }
    if system:
        payload["system"] = system
    if extra:
        payload.update(extra)

    structured_tool_name: str | None = None
    if response_format:
        tool, structured_tool_name = _build_structured_tool_payload(response_format)
        payload["tools"] = [tool]
        payload["tool_choice"] = {"type": "tool", "name": tool["name"]}

    try:
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            default_headers={"anthropic-version": anthropic_version},
        )
        message = client.messages.create(**payload)
    except Exception as e:
        raise RuntimeError(str(e))

    data = message.model_dump()
    structured = _extract_structured_from_blocks(message.content, structured_tool_name)
    if response_format and structured is None:
        raise RuntimeError("Structured output requested, but model did not return tool_use content")

    return {
        "provider": "minimax",
        "model": selected_model,
        "text": _extract_text_from_blocks(message.content),
        "structured": structured,
        "response": data,
    }
