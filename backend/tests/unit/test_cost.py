"""
Unit tests for the cost formula.

Formula (from spec §1.3):
    cost_usd = (tokens_in / 1000 * input_price_per_1k) + (tokens_out / 1000 * output_price_per_1k)

Seed model pricing used here:
    gpt-4o-mini:         input=0.000150, output=0.000600
    claude-3-haiku:      input=0.000250, output=0.001250
    llama3-8b-8192:      input=0.000050, output=0.000080
"""
import pytest

from app.cost import compute_cost


class TestCostFormula:
    def test_gpt4o_mini_basic(self):
        # 1000 in, 500 out → 1*0.000150 + 0.5*0.000600 = 0.000150 + 0.000300 = 0.000450
        cost = compute_cost(1000, 500, 0.000150, 0.000600)
        assert abs(cost - 0.000450) < 1e-9

    def test_gpt4o_mini_large(self):
        # 10000 in, 2000 out → 10*0.000150 + 2*0.000600 = 0.001500 + 0.001200 = 0.002700
        cost = compute_cost(10_000, 2_000, 0.000150, 0.000600)
        assert abs(cost - 0.002700) < 1e-9

    def test_claude_haiku(self):
        # 500 in, 1000 out → 0.5*0.000250 + 1*0.001250 = 0.000125 + 0.001250 = 0.001375
        cost = compute_cost(500, 1_000, 0.000250, 0.001250)
        assert abs(cost - 0.001375) < 1e-9

    def test_groq_llama_free_tier(self):
        # 2000 in, 500 out → 2*0.000050 + 0.5*0.000080 = 0.000100 + 0.000040 = 0.000140
        cost = compute_cost(2_000, 500, 0.000050, 0.000080)
        assert abs(cost - 0.000140) < 1e-9

    def test_zero_tokens(self):
        cost = compute_cost(0, 0, 0.000150, 0.000600)
        assert cost == 0.0

    def test_output_only(self):
        # 0 in, 1000 out → 0 + 1*0.000600 = 0.000600
        cost = compute_cost(0, 1_000, 0.000150, 0.000600)
        assert abs(cost - 0.000600) < 1e-9
