"""Unit tests for the retry utility.

Covers:
  - Succeeds on first attempt → no retry
  - Retries on 429, 502, 503, 504, 408 (retryable codes)
  - Retries on httpx.TimeoutException and httpx.ConnectError
  - Does NOT retry on 400, 401, 403, 404, 422 (non-retryable)
  - Exhausts all attempts and re-raises last error
  - Backoff delay is called with approximately correct value
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
import pytest

from app.reliability.retry import with_retry, _RETRYABLE_STATUS_CODES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    return httpx.HTTPStatusError(
        f"HTTP {status_code}", request=MagicMock(), response=response
    )


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt():
    fn = AsyncMock(return_value="ok")
    result = await with_retry(fn, "arg1", kwarg="v")
    assert result == "ok"
    fn.assert_awaited_once_with("arg1", kwarg="v")


# ---------------------------------------------------------------------------
# Retryable HTTP status codes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", sorted(_RETRYABLE_STATUS_CODES))
async def test_retries_on_retryable_status_code(status_code: int):
    """Should retry once and succeed on the second attempt."""
    exc = _http_error(status_code)
    fn = AsyncMock(side_effect=[exc, "recovered"])

    with patch("app.reliability.retry.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await with_retry(fn, max_attempts=2, base_delay=0.5)

    assert result == "recovered"
    assert fn.await_count == 2
    mock_sleep.assert_awaited_once_with(0.5)


# ---------------------------------------------------------------------------
# Retryable network errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_timeout_exception():
    fn = AsyncMock(side_effect=[httpx.TimeoutException("timed out"), "recovered"])
    with patch("app.reliability.retry.asyncio.sleep", new=AsyncMock()):
        result = await with_retry(fn, max_attempts=2)
    assert result == "recovered"
    assert fn.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_connect_error():
    fn = AsyncMock(side_effect=[httpx.ConnectError("refused"), "recovered"])
    with patch("app.reliability.retry.asyncio.sleep", new=AsyncMock()):
        result = await with_retry(fn, max_attempts=2)
    assert result == "recovered"
    assert fn.await_count == 2


# ---------------------------------------------------------------------------
# Non-retryable HTTP errors — should raise immediately, no retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_does_not_retry_on_client_error(status_code: int):
    exc = _http_error(status_code)
    fn = AsyncMock(side_effect=exc)

    with pytest.raises(httpx.HTTPStatusError):
        await with_retry(fn, max_attempts=2)

    # Must have been called exactly once — no retry.
    fn.assert_awaited_once()


# ---------------------------------------------------------------------------
# Exhausts all attempts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_after_all_attempts_exhausted():
    exc = _http_error(503)
    fn = AsyncMock(side_effect=exc)

    with patch("app.reliability.retry.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(httpx.HTTPStatusError):
            await with_retry(fn, max_attempts=2)

    assert fn.await_count == 2


@pytest.mark.asyncio
async def test_three_attempts_two_retries():
    exc = _http_error(429)
    fn = AsyncMock(side_effect=[exc, exc, "ok"])

    with patch("app.reliability.retry.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await with_retry(fn, max_attempts=3, base_delay=0.5)

    assert result == "ok"
    assert fn.await_count == 3
    # Delays: 0.5 * 2^0=0.5, 0.5 * 2^1=1.0
    assert mock_sleep.await_count == 2
    mock_sleep.assert_any_await(0.5)
    mock_sleep.assert_any_await(1.0)


# ---------------------------------------------------------------------------
# Backoff delay correctness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backoff_delay_is_correct():
    exc = _http_error(503)
    fn = AsyncMock(side_effect=[exc, "ok"])

    captured_delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        captured_delays.append(delay)

    with patch("app.reliability.retry.asyncio.sleep", new=fake_sleep):
        await with_retry(fn, max_attempts=2, base_delay=0.5)

    assert len(captured_delays) == 1
    assert captured_delays[0] == pytest.approx(0.5)
