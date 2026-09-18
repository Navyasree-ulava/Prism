"""Unit tests for LLM analyzer fallback behaviour."""
from unittest.mock import patch

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
