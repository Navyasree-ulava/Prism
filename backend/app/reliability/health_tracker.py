"""In-memory health tracker for provider models.

Tracks consecutive failures per model and temporarily marks a model
unhealthy after 3 consecutive failures. No Redis, no FSM library.

State per model:
    {model_id: {"consecutive_failures": int, "unhealthy_until": datetime | None}}

Recovery behaviour
------------------
After the 60 s cooldown expires, ``is_healthy`` returns ``True`` once
(probe window). The caller MUST call ``record_success`` or
``record_failure`` after the probe attempt:
  - success → fully healthy (counter reset)
  - failure → unhealthy for another 60 s
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock

_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 60


class HealthTracker:
    """Thread-safe, in-memory health tracker for model IDs."""

    def __init__(self) -> None:
        self._state: dict[str, dict] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_healthy(self, model_id: str) -> bool:
        """Return whether the model should receive traffic.

        Returns ``True`` if:
          - the model has never failed, OR
          - fewer than 3 consecutive failures have been recorded, OR
          - the 60 s cooldown window has expired (allows one probe request).

        Returns ``False`` while ``now < unhealthy_until``.
        """
        with self._lock:
            entry = self._state.get(model_id)
            if entry is None:
                return True

            unhealthy_until = entry.get("unhealthy_until")
            if unhealthy_until is None:
                return True

            now = datetime.now(tz=timezone.utc)
            if now >= unhealthy_until:
                # Cooldown expired — allow one probe through.
                # Do NOT reset the counter here; only record_success does that.
                entry["unhealthy_until"] = None
                return True

            return False

    def record_failure(self, model_id: str) -> None:
        """Increment the failure counter; mark unhealthy at threshold."""
        with self._lock:
            entry = self._state.setdefault(
                model_id, {"consecutive_failures": 0, "unhealthy_until": None}
            )
            entry["consecutive_failures"] += 1
            if entry["consecutive_failures"] >= _FAILURE_THRESHOLD:
                entry["unhealthy_until"] = datetime.now(tz=timezone.utc) + timedelta(
                    seconds=_COOLDOWN_SECONDS
                )

    def record_success(self, model_id: str) -> None:
        """Reset the failure counter and clear the unhealthy window."""
        with self._lock:
            self._state[model_id] = {
                "consecutive_failures": 0,
                "unhealthy_until": None,
            }

    # ------------------------------------------------------------------
    # Inspection helpers (useful for tests and admin endpoints)
    # ------------------------------------------------------------------

    def get_state(self, model_id: str) -> dict:
        """Return a copy of the tracking state for *model_id*."""
        with self._lock:
            return dict(self._state.get(model_id, {"consecutive_failures": 0, "unhealthy_until": None}))
