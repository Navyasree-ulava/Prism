"""Unit tests for HealthTracker.

Covers:
  - New model starts healthy
  - 1-2 failures → still healthy
  - 3 failures → unhealthy (cooldown starts)
  - After cooldown expires → probe window (returns True once)
  - Success after probe → fully healthy, counter reset
  - Failure after probe → unhealthy again for another 60s
  - record_success() resets everything mid-run
  - get_state() helper
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.reliability.health_tracker import HealthTracker, _COOLDOWN_SECONDS, _FAILURE_THRESHOLD


def _tracker() -> HealthTracker:
    return HealthTracker()


# ---------------------------------------------------------------------------
# Basic healthy states
# ---------------------------------------------------------------------------


def test_new_model_is_healthy():
    ht = _tracker()
    assert ht.is_healthy("gpt-4o-mini") is True


def test_one_failure_still_healthy():
    ht = _tracker()
    ht.record_failure("model-a")
    assert ht.is_healthy("model-a") is True


def test_two_failures_still_healthy():
    ht = _tracker()
    ht.record_failure("model-a")
    ht.record_failure("model-a")
    assert ht.is_healthy("model-a") is True


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------


def test_three_failures_makes_unhealthy():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")
    assert ht.is_healthy("model-a") is False


def test_failures_do_not_bleed_across_models():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")
    # model-b is completely separate
    assert ht.is_healthy("model-b") is True


# ---------------------------------------------------------------------------
# Cooldown and probe window
# ---------------------------------------------------------------------------


def test_cooldown_expires_and_allows_probe():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")

    # Simulate cooldown expiry by backdating unhealthy_until.
    future_past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    ht._state["model-a"]["unhealthy_until"] = future_past

    # Should allow one probe through.
    assert ht.is_healthy("model-a") is True
    # unhealthy_until cleared after probe check.
    assert ht._state["model-a"]["unhealthy_until"] is None


def test_success_after_probe_fully_resets():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")
    # Expire cooldown.
    ht._state["model-a"]["unhealthy_until"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    ht.is_healthy("model-a")  # probe
    ht.record_success("model-a")

    state = ht.get_state("model-a")
    assert state["consecutive_failures"] == 0
    assert state["unhealthy_until"] is None
    assert ht.is_healthy("model-a") is True


def test_failure_after_probe_extends_cooldown():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")
    # Expire cooldown.
    ht._state["model-a"]["unhealthy_until"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    ht.is_healthy("model-a")  # probe — clears unhealthy_until
    # Probe attempt fails.
    ht.record_failure("model-a")

    # Counter is now _FAILURE_THRESHOLD + 1 → unhealthy again.
    assert ht.is_healthy("model-a") is False


# ---------------------------------------------------------------------------
# record_success() mid-run
# ---------------------------------------------------------------------------


def test_record_success_resets_counter():
    ht = _tracker()
    ht.record_failure("model-a")
    ht.record_failure("model-a")
    ht.record_success("model-a")

    state = ht.get_state("model-a")
    assert state["consecutive_failures"] == 0
    assert state["unhealthy_until"] is None
    assert ht.is_healthy("model-a") is True


def test_record_success_clears_unhealthy_window():
    ht = _tracker()
    for _ in range(_FAILURE_THRESHOLD):
        ht.record_failure("model-a")
    assert ht.is_healthy("model-a") is False  # confirm unhealthy
    ht.record_success("model-a")
    assert ht.is_healthy("model-a") is True


# ---------------------------------------------------------------------------
# get_state() helper
# ---------------------------------------------------------------------------


def test_get_state_defaults_for_unknown_model():
    ht = _tracker()
    state = ht.get_state("never-seen")
    assert state["consecutive_failures"] == 0
    assert state["unhealthy_until"] is None
