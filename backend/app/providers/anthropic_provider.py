"""Anthropic provider adapter (translates to/from the Messages API)."""
import json
import uuid

import httpx

from app.config import settings
from app.providers.base import LLMProvider
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse, ChatResponseChoice

_ANTHROPIC_BASE = "https://api.anthropic.com/v1"
_ANTHROPIC_VERSION = "2023-06-01"
# Default max_tokens for Anthropic (required field, unlike OpenAI).
_DEFAULT_MAX_TOKENS = 1024


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"

    async def health_check(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        # Anthropic separates the system prompt from the conversation turns.
        system_parts = [m.content for m in request.messages if m.role == "system"]
        turns = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]

        payload: dict = {
            "model": request.model,
            "messages": turns,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_ANTHROPIC_BASE}/messages",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Map Anthropic response shape → OpenAI-compatible ChatResponse.
        content_text = "".join(
            block.get("text", "") for block in data.get("content", [])
        )
        choice = ChatResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason=data.get("stop_reason", "stop"),
        )

        usage = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            model=data.get("model", request.model),
            choices=[choice],
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
        )

    async def stream(self, request: ChatRequest):  # type: ignore[override]
        system_parts = [m.content for m in request.messages if m.role == "system"]
        turns = [
            {"role": m.role, "content": m.content}
            for m in request.messages if m.role != "system"
        ]
        payload: dict = {
            "model": request.model,
            "messages": turns,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{_ANTHROPIC_BASE}/messages",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                text = data.get("delta", {}).get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
