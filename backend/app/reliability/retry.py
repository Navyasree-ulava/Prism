"""Async retry utility for provider calls.

Retries only on transient/overload errors:
    - HTTP status codes: 408, 429, 502, 503, 504
    - Network-level errors: httpx.TimeoutException, httpx.ConnectError

Does NOT retry on client errors (400, 401, 403, 404, 422) — those indicate
a bad request or auth issue and retrying would not help.

Configuration
-------------
max_attempts : 2   (1 original + 1 retry)
base_delay   : 0.5 s
backoff      : exponential — delay = base_delay * (2 ** attempt_index)
               attempt 0 → no wait (first try)
               attempt 1 → 0.5 s wait before second try
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Status codes that warrant a retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    """Return True if *exc* should trigger a retry attempt."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.ConnectError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


async def with_retry(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 2,
    base_delay: float = 0.5,
    **kwargs: Any,
) -> T:
    """Call *fn* with *args*/*kwargs*, retrying on transient errors.

    Args:
        fn:           Async callable to invoke.
        *args:        Positional arguments forwarded to *fn*.
        max_attempts: Total number of attempts (default 2 → 1 retry).
        base_delay:   Base backoff delay in seconds (default 0.5).
        **kwargs:     Keyword arguments forwarded to *fn*.

    Returns:
        The return value of *fn* on a successful attempt.

    Raises:
        The last exception if all attempts are exhausted, or the first
        non-retryable exception immediately.
    """
    last_exc: BaseException | None = None

    for attempt in range(max_attempts):
        if attempt > 0:
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Retry attempt %d/%d after %.1fs (last error: %s)",
                attempt,
                max_attempts - 1,
                delay,
                last_exc,
            )
            await asyncio.sleep(delay)

        try:
            return await fn(*args, **kwargs)
        except BaseException as exc:
            if not _is_retryable(exc):
                raise
            last_exc = exc
            logger.warning("Retryable error on attempt %d: %s", attempt + 1, exc)

    # All attempts exhausted — re-raise the last retryable error.
    raise last_exc  # type: ignore[misc]
