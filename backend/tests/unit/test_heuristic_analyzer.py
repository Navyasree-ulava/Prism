"""Unit tests for heuristic_analyzer.py"""
import pytest

from app.analyzer.heuristic_analyzer import analyze


class TestTaskTypeClassification:
    def test_coding_strong_backtick_fence(self):
        result = analyze("```python\ndef hello():\n    pass\n```\nWhat does this do?")
        assert result.task_type == "coding"
        assert result.confidence == 0.9

    def test_coding_strong_write_function(self):
        result = analyze("Write a function to reverse a linked list in Python")
        assert result.task_type == "coding"
        assert result.confidence == 0.9

    def test_coding_strong_def_keyword(self):
        result = analyze("def add(a, b): return a + b — can you improve this?")
        assert result.task_type == "coding"

    def test_coding_weak_keyword_bug(self):
        result = analyze("There is a bug in my script")
        assert result.task_type == "coding"
        assert result.confidence == 0.7

    def test_summarization_keyword(self):
        result = analyze("Summarize this research paper for me")
        assert result.task_type == "summarization"
        assert result.confidence == 0.9

    def test_summarization_tldr(self):
        result = analyze("Give me a tl;dr of the following text")
        assert result.task_type == "summarization"

    def test_qa_short_question(self):
        result = analyze("What is the capital of France?")
        assert result.task_type == "qa"
        assert result.confidence == 0.9

    def test_general_fallback(self):
        result = analyze("Tell me an interesting story about space exploration")
        assert result.task_type == "general"
        assert result.confidence == 0.6


class TestComplexity:
    def test_low_complexity_short(self):
        result = analyze("Hello how are you?")
        assert result.complexity == "low"

    def test_medium_complexity(self):
        prompt = " ".join(["word"] * 200)
        result = analyze(prompt)
        assert result.complexity == "medium"

    def test_high_complexity_long(self):
        prompt = " ".join(["word"] * 600)
        result = analyze(prompt)
        assert result.complexity == "high"

    def test_high_complexity_multi_step(self):
        prompt = "First, open the file. Then, read the content. Finally, close it."
        result = analyze(prompt)
        assert result.complexity == "high"


class TestEstimatedTokens:
    def test_token_estimate_formula(self):
        prompt = " ".join(["word"] * 100)
        result = analyze(prompt)
        assert result.estimated_input_tokens == 130  # 100 * 1.3

    def test_context_low(self):
        result = analyze("Short prompt")
        assert result.context_requirement == "low"

    def test_context_high(self):
        prompt = " ".join(["word"] * 2500)   # 2500 * 1.3 = 3250 > 3000
        result = analyze(prompt)
        assert result.context_requirement == "high"


class TestRequiredCapabilities:
    def test_coding_capabilities(self):
        result = analyze("Write a class to manage a queue")
        assert set(result.required_capabilities) == {"coding", "reasoning"}

    def test_summarization_capabilities(self):
        result = analyze("Summarize this document")
        assert "summarization" in result.required_capabilities

    def test_qa_capabilities(self):
        result = analyze("What is 2 + 2?")
        assert "qa" in result.required_capabilities

    def test_output_schema_valid(self):
        result = analyze("anything")
        assert result.task_type in {"coding", "summarization", "qa", "general"}
        assert result.complexity in {"low", "medium", "high"}
        assert result.context_requirement in {"low", "medium", "high"}
        assert 0.0 <= result.confidence <= 1.0
        assert result.estimated_input_tokens >= 0
        assert isinstance(result.required_capabilities, list)
