"""LLM-based prompt analyzer — single cheap LLM call returning AnalysisResult JSON.

Used when ANALYZER_MODE=llm. Falls back to heuristic analyzer if no API key
is configured or the LLM call fails (strict=False, the default).

strict=True (used by the eval harness) instead propagates the underlying
error, so callers can tell a real LLM classification apart from a fallback.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from app.analyzer.heuristic_analyzer import AnalysisResult, analyze as heuristic_analyze
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You classify user prompts for an LLM routing gateway.
Return ONLY valid JSON with these exact keys:
{
  "task_type": "coding" | "summarization" | "qa" | "general",
  "complexity": "low" | "medium" | "high",
  "required_capabilities": ["..."],
  "context_requirement": "low" | "medium" | "high",
  "estimated_input_tokens": <integer>,
  "confidence": <float 0.0-1.0>
}

Capability options: general, coding, reasoning, summarization, qa, long_context.
Map task_type to capabilities: coding→[coding,reasoning]; summarization→[summarization,general];
qa→[qa,general]; general→[general].
For estimated_input_tokens, compute word_count × 1.3 yourself and write only the
final rounded integer (e.g. 650) — never a formula or expression."""


def _extract_json(text: str) -> dict:
    """Parse JSON from a raw LLM response, tolerating markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


async def analyze(prompt: str, *, strict: bool = False) -> AnalysisResult:
    """Classify *prompt* via a cheap LLM call; fall back to heuristic on failure.

    Args:
        prompt:  Raw user prompt to classify.
        strict:  If True, raise on any failure instead of falling back to the
                 heuristic analyzer. Used by the eval harness so measured
                 "LLM accuracy" only reflects genuine LLM classifications.
    """
    if not settings.groq_api_key and not settings.openai_api_key:
        if strict:
            raise RuntimeError("LLM analyzer: no API key configured")
        logger.warning("No API key for LLM analyzer — falling back to heuristic")
        return heuristic_analyze(prompt)

    provider = "groq" if settings.groq_api_key else "openai"
    if provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        # llama3-8b-8192 was decommissioned by Groq (Sept 2026); allam-2-7b is
        # the smallest currently-available model that reliably returns our JSON.
        model = "allam-2-7b"
        api_key = settings.groq_api_key
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"
        api_key = settings.openai_api_key

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 256,
        # JSON mode: guarantees syntactically valid JSON (blocks model-echoed
        # formulas like "estimated_input_tokens": (1000 * 1.3)).
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        return AnalysisResult.model_validate(parsed)
    except Exception as exc:
        if strict:
            raise
        logger.warning("LLM analyzer failed (%s) — falling back to heuristic", exc)
        return heuristic_analyze(prompt)
