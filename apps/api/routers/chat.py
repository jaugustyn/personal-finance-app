"""POST /chat — hybrid LLM assistant (heuristic router + Ollama fallback)."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.config import get_settings
from finance.db import get_session
from finance.llm.client import is_available as ollama_is_available
from finance.llm.router import answer
from finance.llm.tools import TOOLS
from finance.profile.service import get_assistant_llm_model, is_assistant_llm_enabled

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    previous_tool: str | None = None
    previous_tool_args: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    tool: str | None
    tool_args: dict[str, Any] | None
    data: dict[str, Any] | None
    source: str


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    res = answer(
        req.question,
        session,
        previous_tool=req.previous_tool,
        previous_tool_args=req.previous_tool_args,
    )
    return ChatResponse(
        answer=res.answer,
        tool=res.tool,
        tool_args=res.tool_args,
        data=res.data,
        source=res.source,
    )


@router.get("/health")
def chat_health(session: Session = Depends(get_session)) -> dict[str, Any]:
    settings = get_settings()
    user_enabled = is_assistant_llm_enabled(session)
    model = get_assistant_llm_model(session) or settings.ollama_model
    available = (
        ollama_is_available(model=model)
        if settings.llm_enabled and user_enabled
        else False
    )
    return {
        "ollama_available": available,
        "llm_enabled": settings.llm_enabled,
        "assistant_llm_enabled": user_enabled,
        "mode": (
            "hybrid"
            if settings.llm_enabled and user_enabled and available
            else "deterministic"
        ),
        "deterministic_tools": sorted(TOOLS),
    }
