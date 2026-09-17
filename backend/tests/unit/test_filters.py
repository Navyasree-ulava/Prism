"""Unit tests for routing/filters.py"""
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.routing.filters import filter_by_capability, filter_by_health


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _Model:
    id: str
    capabilities: object  # list[str] | str


def _model(id: str, caps) -> _Model:
    return _Model(id=id, capabilities=caps)


# ---------------------------------------------------------------------------
# filter_by_capability
# ---------------------------------------------------------------------------


class TestFilterByCapability:
    def test_empty_candidates_returns_empty(self):
        assert filter_by_capability([], ["coding"]) == []

    def test_no_required_returns_all(self):
        models = [_model("m1", ["general"])]
        assert filter_by_capability(models, []) == models

    def test_full_superset_included(self):
        m = _model("m1", ["coding", "reasoning", "general"])
        assert filter_by_capability([m], ["coding", "reasoning"]) == [m]

    def test_partial_match_excluded(self):
        m = _model("m1", ["coding"])
        assert filter_by_capability([m], ["coding", "reasoning"]) == []

    def test_no_match_excluded(self):
        m = _model("m1", ["general"])
        assert filter_by_capability([m], ["coding"]) == []

    def test_mixed_candidates_correctly_split(self):
        good = _model("good", ["coding", "reasoning"])
        bad = _model("bad", ["general"])
        result = filter_by_capability([good, bad], ["coding"])
        assert result == [good]

    def test_string_caps_json_format(self):
        """SQLite stores capabilities as JSON string — filters must handle it."""
        m = _model("m1", '["coding", "reasoning"]')  # type: ignore[arg-type]
        assert filter_by_capability([m], ["coding"]) == [m]

    def test_string_caps_python_repr_format(self):
        """Legacy Python repr format e.g. \"['coding', 'reasoning']\"."""
        m = _model("m1", "['coding', 'reasoning']")  # type: ignore[arg-type]
        assert filter_by_capability([m], ["reasoning"]) == [m]


# ---------------------------------------------------------------------------
# filter_by_health
# ---------------------------------------------------------------------------


class TestFilterByHealth:
    def test_no_tracker_passes_all(self):
        models = [_model("m1", []), _model("m2", [])]
        assert filter_by_health(models) == models

    def test_none_tracker_passes_all(self):
        models = [_model("m1", [])]
        assert filter_by_health(models, health_tracker=None) == models

    def test_healthy_model_passes(self):
        m = _model("m1", [])
        tracker = MagicMock()
        tracker.is_healthy.return_value = True
        assert filter_by_health([m], tracker) == [m]

    def test_unhealthy_model_excluded(self):
        m = _model("m1", [])
        tracker = MagicMock()
        tracker.is_healthy.return_value = False
        assert filter_by_health([m], tracker) == []

    def test_mixed_health(self):
        healthy = _model("ok", [])
        sick = _model("sick", [])
        tracker = MagicMock()
        tracker.is_healthy.side_effect = lambda id: id == "ok"
        result = filter_by_health([healthy, sick], tracker)
        assert result == [healthy]
