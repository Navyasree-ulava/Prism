"""Groq provider adapter.

Groq exposes an OpenAI-compatible API, so this is a thin wrapper that
points to the Groq base URL instead of api.openai.com.
"""
import json
import uuid

import httpx

from app.config import settings
from app.providers.base import LLMProvider
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse, ChatResponseChoice

_GROQ_BASE = "https://api.groq.com/openai/v1"


class GroqProvider(LLMProvider):
    provider_name = "groq"

    async def health_check(self) -> bool:
        return bool(settings.groq_api_key)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_GROQ_BASE}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = [
            ChatResponseChoice(
                index=c["index"],
                message=ChatMessage(
                    role=c["message"]["role"],
                    content=c["message"]["content"],
                ),
                finish_reason=c.get("finish_reason", "stop"),
            )
            for c in data["choices"]
        ]

        return ChatResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            model=data.get("model", request.model),
            choices=choices,
            usage=data.get("usage", {}),
        )

    async def stream(self, request: ChatRequest):  # type: ignore[override]
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{_GROQ_BASE}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
