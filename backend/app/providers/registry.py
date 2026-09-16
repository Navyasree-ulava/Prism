"""Provider registry — maps provider name strings to adapter instances."""
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.groq_provider import GroqProvider
from app.providers.openai_provider import OpenAIProvider

_REGISTRY: dict[str, LLMProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "groq": GroqProvider(),
}


def get_provider(provider_name: str) -> LLMProvider:
    """Return the adapter for *provider_name*.

    Raises:
        ValueError: if *provider_name* is not registered.
    """
    try:
        return _REGISTRY[provider_name]
    except KeyError:
        supported = ", ".join(_REGISTRY)
        raise ValueError(
            f"Unknown provider '{provider_name}'. Supported: {supported}"
        )
