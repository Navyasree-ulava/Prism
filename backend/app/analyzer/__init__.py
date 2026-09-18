from app.analyzer.heuristic_analyzer import AnalysisResult
from app.analyzer.heuristic_analyzer import analyze as heuristic_analyze
from app.config import settings


async def analyze_prompt(prompt: str) -> AnalysisResult:
    """Run the configured analyzer (heuristic or LLM) on *prompt*."""
    if settings.analyzer_mode == "llm":
        from app.analyzer.llm_analyzer import analyze as llm_analyze

        return await llm_analyze(prompt)
    return heuristic_analyze(prompt)


__all__ = ["AnalysisResult", "analyze_prompt", "heuristic_analyze"]
