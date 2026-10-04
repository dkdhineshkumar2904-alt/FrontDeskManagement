"""Unit tests for rate-limiting, Retry-After parsing, jitter, and retry policies."""

import time
from email.utils import formatdate
from unittest.mock import AsyncMock

import httpx
import pytest

from freshdesk_mcp.exceptions import (
    FreshdeskAPIError,
    FreshdeskAuthenticationError,
    FreshdeskNotFoundError,
    FreshdeskPermissionError,
    FreshdeskRateLimitError,
    FreshdeskTimeoutError,
    FreshdeskValidationError,
)
from freshdesk_mcp.retry import (
    RetryPolicy,
    calculate_jittered_backoff,
    parse_retry_after,
)


def test_parse_retry_after_numeric() -> None:
    """Verify numeric seconds in Retry-After header are parsed properly."""
    assert parse_retry_after("15") == 15.0
    assert parse_retry_after("2.5") == 2.5
    assert parse_retry_after("0") == 0.1  # Clamped to min 0.1s
    assert parse_retry_after(None, default_val=3.0) == 3.0
    assert parse_retry_after("", default_val=2.0) == 2.0


def test_parse_retry_after_http_date() -> None:
    """Verify HTTP date format (RFC 2822) in Retry-After header is parsed correctly."""
    future_time = time.time() + 12.0
    http_date = formatdate(future_time, usegmt=True)
    parsed = parse_retry_after(http_date)
    assert 10.0 <= parsed <= 14.0


def test_parse_retry_after_cap() -> None:
    """Verify excessive Retry-After is capped to maximum limit."""
    assert parse_retry_after("3600", max_cap=30.0) == 30.0


def test_calculate_jittered_backoff() -> None:
    """Verify backoff calculation stays within bounded random range."""
    for attempt in range(4):
        val = calculate_jittered_backoff(attempt, base_delay=0.1, max_delay=5.0)
        assert 0.1 <= val <= 5.0


@pytest.mark.asyncio
async def test_retry_success_first_try() -> None:
    """Verify operation succeeds immediately when response is 200 OK."""
    policy = RetryPolicy(max_retries=2, base_delay=0.01)
    mock_resp = httpx.Response(200, json={"status": "ok"})
    mock_op = AsyncMock(return_value=mock_resp)

    res = await policy.execute(mock_op)
    assert res.status_code == 200
    assert mock_op.call_count == 1


@pytest.mark.asyncio
async def test_retry_transient_503_then_success() -> None:
    """Verify retry handles transient 503 and returns on subsequent 200."""
    policy = RetryPolicy(max_retries=2, base_delay=0.01)
    resp_503 = httpx.Response(503, text="Service Unavailable")
    resp_200 = httpx.Response(200, json={"data": "ready"})
    mock_op = AsyncMock(side_effect=[resp_503, resp_200])

    res = await policy.execute(mock_op)
    assert res.status_code == 200
    assert mock_op.call_count == 2


@pytest.mark.asyncio
async def test_retry_rate_limit_429_exhaustion() -> None:
    """Verify persistent 429 rate limit raises FreshdeskRateLimitError when retries exhausted."""
    policy = RetryPolicy(max_retries=2, base_delay=0.01)
    resp_429 = httpx.Response(
        429, headers={"Retry-After": "0.01"}, json={"message": "Limit exceeded"}
    )
    mock_op = AsyncMock(return_value=resp_429)

    with pytest.raises(FreshdeskRateLimitError) as exc_info:
        await policy.execute(mock_op)
    assert exc_info.value.error_code == "RATE_LIMIT_EXCEEDED"
    assert exc_info.value.retryable is True
    # Initial attempt + 2 retries = 3 attempts total
    assert mock_op.call_count == 3


@pytest.mark.asyncio
async def test_retry_server_500_exhaustion() -> None:
    """Verify persistent 500 error raises FreshdeskAPIError."""
    policy = RetryPolicy(max_retries=1, base_delay=0.01)
    resp_500 = httpx.Response(500, text="Internal Server Error")
    mock_op = AsyncMock(return_value=resp_500)

    with pytest.raises(FreshdeskAPIError) as exc_info:
        await policy.execute(mock_op)
    assert exc_info.value.status_code == 500
    assert mock_op.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,expected_exception,expected_code",
    [
        (401, FreshdeskAuthenticationError, "AUTHENTICATION_FAILED"),
        (403, FreshdeskPermissionError, "PERMISSION_DENIED"),
        (404, FreshdeskNotFoundError, "RESOURCE_NOT_FOUND"),
        (400, FreshdeskValidationError, "VALIDATION_ERROR"),
        (422, FreshdeskValidationError, "VALIDATION_ERROR"),
    ],
)
async def test_non_retryable_client_errors_fail_fast(
    status_code: int,
    expected_exception: type[Exception],
    expected_code: str,
) -> None:
    """Verify 4xx client errors fail immediately on first attempt without retrying."""
    policy = RetryPolicy(max_retries=3, base_delay=0.01)
    resp = httpx.Response(status_code, json={"message": f"Client error {status_code}"})
    mock_op = AsyncMock(return_value=resp)

    with pytest.raises(expected_exception) as exc_info:
        await policy.execute(mock_op)
    assert exc_info.value.error_code == expected_code  # type: ignore[attr-defined]
    # Fast-fail must NOT retry!
    assert mock_op.call_count == 1


@pytest.mark.asyncio
async def test_retry_network_timeout_exhaustion() -> None:
    """Verify connection timeouts retry and eventually raise FreshdeskTimeoutError."""
    policy = RetryPolicy(max_retries=1, base_delay=0.01)
    req = httpx.Request("GET", "https://testcorp.freshdesk.com/api/v2/tickets")
    mock_op = AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out", request=req))

    with pytest.raises(FreshdeskTimeoutError) as exc_info:
        await policy.execute(mock_op)
    assert exc_info.value.error_code == "REQUEST_TIMEOUT"
    assert mock_op.call_count == 2
