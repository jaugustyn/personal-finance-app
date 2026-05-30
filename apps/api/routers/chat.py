"""POST /chat — hybrid LLM assistant (heuristic router + Ollama fallback)."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.llm.client import is_available as ollama_is_available
from finance.llm.router import answer

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    use_llm_summary: bool = False


class ChatResponse(BaseModel):
    answer: str
    tool: str | None
    tool_args: dict[str, Any] | None
    data: dict[str, Any] | None
    source: str


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    res = answer(req.question, session, use_llm_summary=req.use_llm_summary)
    return ChatResponse(
        answer=res.answer,
        tool=res.tool,
        tool_args=res.tool_args,
        data=res.data,
        source=res.source,
    )


@router.get("/health")
def chat_health() -> dict[str, Any]:
    return {"ollama_available": ollama_is_available()}
