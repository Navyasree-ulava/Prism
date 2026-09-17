"""OpenAI-compatible chat completion schemas + Phase 3 routing extension."""
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str       # "system" | "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    model: str | None = None    # None → routing engine selects
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class ChatResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


# ---------------------------------------------------------------------------
# Phase 3 routing extension
# ---------------------------------------------------------------------------


class RoutingCandidate(BaseModel):
    model: str
    score: float


class RoutingInfo(BaseModel):
    selected_model: str
    strategy: str
    reason: str
    confidence: float
    candidates: list[RoutingCandidate]
    fallback_used: bool = False
    cost_usd: float
    latency_ms: int


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[ChatResponseChoice]
    usage: dict
    routing: RoutingInfo | None = None
