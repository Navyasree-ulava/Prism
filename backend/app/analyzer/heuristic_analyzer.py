"""Heuristic prompt analyzer — pure function, no I/O, no LLM calls.

Classifies a prompt into task_type, complexity, required capabilities,
context requirement, estimated token count, and confidence score.
"""
import re

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Output schema (fixed — used by routing engine)
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    task_type: str              # "coding" | "summarization" | "qa" | "general"
    complexity: str             # "low" | "medium" | "high"
    required_capabilities: list[str]
    context_requirement: str    # "low" | "medium" | "high"
    estimated_input_tokens: int
    confidence: float           # 0.0–1.0


# ---------------------------------------------------------------------------
# Classification patterns
# ---------------------------------------------------------------------------

_CODING_STRONG = re.compile(
    r"```"
    r"|`{3}"
    r"|\bdef \b"
    r"|\bclass \b"
    r"|\bwrite\s+a\s+(function|class|script|program|method)\b"
    r"|\b(implement|refactor|fix|debug)\b.{0,60}\b(function|class|bug|error|issue|code)\b",
    re.IGNORECASE | re.DOTALL,
)
_CODING_WEAK = re.compile(
    r"\b(function|bug|error|debug|script|algorithm|code|syntax)\b",
    re.IGNORECASE,
)
_SUMMARIZATION = re.compile(
    r"\b(summarize|summary|tl;dr|tldr|condense|brief|overview|recap)\b",
    re.IGNORECASE,
)
_MULTI_STEP = re.compile(
    r"(first|firstly).{1,200}(then|next|secondly).{1,200}(finally|lastly|lastly)"
    r"|(\d+[.)]\s+.+\n?){2,}",
    re.IGNORECASE | re.DOTALL,
)

# Capability sets per task type
_CAPABILITY_MAP: dict[str, list[str]] = {
    "coding":        ["coding", "reasoning"],
    "summarization": ["summarization", "general"],
    "qa":            ["qa", "general"],
    "general":       ["general"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze(prompt: str) -> AnalysisResult:
    """Classify *prompt* and return an AnalysisResult."""
    words = prompt.split()
    word_count = len(words)
    estimated_tokens = int(word_count * 1.3)

    # --- Task type & confidence ---
    if _CODING_STRONG.search(prompt):
        task_type, confidence = "coding", 0.9
    elif _SUMMARIZATION.search(prompt):
        task_type, confidence = "summarization", 0.9
    elif len(prompt.strip()) < 100 and prompt.strip().endswith("?"):
        task_type, confidence = "qa", 0.9
    elif _CODING_WEAK.search(prompt):
        task_type, confidence = "coding", 0.7
    else:
        task_type, confidence = "general", 0.6

    # --- Complexity ---
    if word_count > 500 or _MULTI_STEP.search(prompt):
        complexity = "high"
    elif word_count > 100:
        complexity = "medium"
    else:
        complexity = "low"

    # --- Context requirement ---
    if estimated_tokens > 3000:
        context_requirement = "high"
    elif estimated_tokens > 1000:
        context_requirement = "medium"
    else:
        context_requirement = "low"

    return AnalysisResult(
        task_type=task_type,
        complexity=complexity,
        required_capabilities=_CAPABILITY_MAP[task_type],
        context_requirement=context_requirement,
        estimated_input_tokens=estimated_tokens,
        confidence=confidence,
    )
