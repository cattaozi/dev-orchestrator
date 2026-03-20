from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import inference_service

router = APIRouter(prefix="/api/llm", tags=["llm"])


class LlmMessagesRequest(BaseModel):
    model: str | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    system: str | None = None
    messages: list[dict[str, Any]]
    extra: dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None


@router.post("/messages")
def call_llm_messages(body: LlmMessagesRequest):
    try:
        return inference_service.call_messages_api(
            model=body.model,
            max_tokens=body.max_tokens,
            system=body.system,
            messages=body.messages,
            extra=body.extra,
            response_format=body.response_format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
