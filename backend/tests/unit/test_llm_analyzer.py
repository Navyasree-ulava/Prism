"""Unit tests for LLM analyzer fallback behaviour."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.analyzer.heuristic_analyzer import analyze as heuristic_analyze
from app.analyzer.llm_analyzer import analyze as llm_analyze


@pytest.mark.asyncio
async def test_llm_analyzer_falls_back_without_api_key():
    with patch("app.analyzer.llm_analyzer.settings") as mock_settings:
        mock_settings.groq_api_key = ""
        mock_settings.openai_api_key = ""
        result = await llm_analyze("Write a Python function to sort a list")
    expected = heuristic_analyze("Write a Python function to sort a list")
    assert result.task_type == expected.task_type
    assert result.complexity == expected.complexity


@pytest.mark.asyncio
async def test_llm_analyzer_strict_raises_without_api_key():
    """strict=True must not silently substitute heuristic results."""
    with patch("app.analyzer.llm_analyzer.settings") as mock_settings:
        mock_settings.groq_api_key = ""
        mock_settings.openai_api_key = ""
        with pytest.raises(RuntimeError, match="no API key"):
            await llm_analyze("Write a Python function to sort a list", strict=True)


@pytest.mark.asyncio
async def test_llm_analyzer_strict_propagates_provider_failure():
    """strict=True must surface provider errors instead of falling back."""
    with patch("app.analyzer.llm_analyzer.settings") as mock_settings:
        mock_settings.groq_api_key = "test-key"
        mock_settings.openai_api_key = ""
        with patch(
            "httpx.AsyncClient.post",
            new=AsyncMock(side_effect=httpx.HTTPStatusError(
                "429",
                request=httpx.Request("POST", "https://api.groq.com"),
                response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com")),
            )),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await llm_analyze("What is 2+2?", strict=True)
            # Non-strict (production path) still falls back to heuristic.
            result = await llm_analyze("What is 2+2?")
    assert result.task_type == heuristic_analyze("What is 2+2?").task_type


@pytest.mark.asyncio
async def test_llm_analyzer_requests_json_mode():
    """Payload must use JSON mode so formula-echoed output can't break parsing."""
    captured: dict = {}

    class _FakeResponse:
        def raise_for_status(self):  # noqa: D102
            return None

        def json(self):  # noqa: D102
            return {"choices": [{"message": {"content":
                '{"task_type":"qa","complexity":"low","required_capabilities":["qa"],'
                '"context_requirement":"low","estimated_input_tokens":13,"confidence":0.9}'}}]}

    async def _fake_post(self, url, json=None, headers=None):  # noqa: A002
        captured.update({"url": url, "payload": json})
        return _FakeResponse()

    with patch("app.analyzer.llm_analyzer.settings") as mock_settings:
        mock_settings.groq_api_key = "test-key"
        mock_settings.openai_api_key = ""
        with patch("httpx.AsyncClient.post", new=_fake_post):
            result = await llm_analyze("What is the capital of France?")

    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert result.task_type == "qa"
