"""Abstract base class for all LLM provider adapters."""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.schemas.chat import ChatRequest, ChatResponse


class LLMProvider(ABC):
    provider_name: str = ""

    @abstractmethod
    async def generate(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat completion request and return a full response."""

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:  # type: ignore[return]
        """Streaming is not implemented until Phase 3."""
        raise NotImplementedError("Streaming is not supported in Phase 2.")
        # Make this a proper async generator so the return type is honoured.
        # The yield is unreachable but satisfies the AsyncIterator contract.
        yield  # pragma: no cover

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable / properly configured."""
