"""Rate limiting and retry strategy for Freshdesk API interactions.

Implements exponential backoff with full jitter, Retry-After header parsing,
deadline awareness, and concurrency throttling.
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

from freshdesk_mcp.exceptions import (
    FreshdeskAPIError,
    FreshdeskAuthenticationError,
    FreshdeskNotFoundError,
    FreshdeskPermissionError,
    FreshdeskRateLimitError,
    FreshdeskTimeoutError,
    FreshdeskValidationError,
)

logger = logging.getLogger("freshdesk_mcp.retry")

T = TypeVar("T")

# Non-retryable HTTP status codes
NON_RETRYABLE_STATUSES = {400, 401, 403, 404, 422}

# Retryable HTTP status codes
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def parse_retry_after(
    header_val: str | None, default_val: float = 1.0, max_cap: float = 60.0
) -> float:
    """Parse HTTP Retry-After header value (either seconds or HTTP date)."""
    if not header_val:
        return default_val

    header_str = header_val.strip()
    # Try parsing as integer seconds
    try:
        seconds = float(header_str)
        return min(max(0.1, seconds), max_cap)
    except ValueError:
        pass

    # Try parsing as HTTP date (RFC 2822 / 7231)
    try:
        dt = parsedate_to_datetime(header_str)
        now = time.time()
        diff = dt.timestamp() - now
        return min(max(0.1, diff), max_cap)
    except Exception:
        return default_val


def calculate_jittered_backoff(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
) -> float:
    """Calculate exponential backoff with full jitter.

    Formula: sleep = Uniform(0, min(max_delay, base_delay * 2^attempt))
    """
    ceiling = min(max_delay, base_delay * (2**attempt))
    return random.uniform(0.1, ceiling)


class RetryPolicy:
    """Reusable retry and concurrency controller for Freshdesk API calls."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        concurrency_limit: int = 5,
        total_timeout: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.total_timeout = total_timeout

    async def execute(
        self,
        operation: Callable[[], Awaitable[httpx.Response]],
        operation_name: str = "freshdesk_request",
    ) -> httpx.Response:
        """Execute an asynchronous HTTP operation with concurrency limiting and retries.

        Handles 429, 5xx, and network timeouts. Immediately bubbles 401, 403, 404, 400, 422.
        """
        deadline = time.time() + self.total_timeout
        attempt = 0

        async with self.semaphore:
            while True:
                remaining_time = deadline - time.time()
                if remaining_time <= 0:
                    raise FreshdeskTimeoutError(
                        f"Retry budget exhausted for {operation_name} after {attempt} attempts."
                    )

                try:
                    response = await operation()

                    # Handle successful responses (2xx)
                    if response.is_success:
                        return response

                    status = response.status_code

                    # Fast-fail non-retryable client errors
                    if status in NON_RETRYABLE_STATUSES:
                        self._handle_client_error(response)

                    # Handle 429 rate limit
                    if status == 429:
                        if attempt >= self.max_retries:
                            retry_after_hdr = response.headers.get("Retry-After")
                            parsed_after = (
                                parse_retry_after(retry_after_hdr) if retry_after_hdr else None
                            )
                            raise FreshdeskRateLimitError(
                                message=f"Rate limit exceeded on {operation_name}. Max retries ({self.max_retries}) exhausted.",
                                retry_after=parsed_after,
                                details={"attempts": attempt + 1},
                            )

                        retry_after_hdr = response.headers.get("Retry-After")
                        delay = parse_retry_after(
                            retry_after_hdr,
                            default_val=calculate_jittered_backoff(
                                attempt, self.base_delay, self.max_delay
                            ),
                        )
                        logger.warning(
                            "Freshdesk rate limit (429) hit on %s. Backing off for %.2fs (attempt %d/%d)",
                            operation_name,
                            delay,
                            attempt + 1,
                            self.max_retries,
                        )
                        attempt += 1
                        await asyncio.sleep(min(delay, max(0.1, deadline - time.time())))
                        continue

                    # Handle 5xx server errors
                    if status in RETRYABLE_STATUSES or status >= 500:
                        if attempt >= self.max_retries:
                            raise FreshdeskAPIError(
                                message=f"Freshdesk server returned HTTP {status} for {operation_name}. Max retries exhausted.",
                                status_code=status,
                                retryable=True,
                                details={"attempts": attempt + 1},
                            )

                        delay = calculate_jittered_backoff(attempt, self.base_delay, self.max_delay)
                        logger.warning(
                            "Freshdesk server error (HTTP %d) on %s. Retrying in %.2fs (attempt %d/%d)",
                            status,
                            operation_name,
                            delay,
                            attempt + 1,
                            self.max_retries,
                        )
                        attempt += 1
                        await asyncio.sleep(min(delay, max(0.1, deadline - time.time())))
                        continue

                    # Any other unexpected status code
                    raise FreshdeskAPIError(
                        message=f"Freshdesk API returned unexpected HTTP status {status}.",
                        status_code=status,
                        retryable=False,
                    )

                except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
                    if attempt >= self.max_retries:
                        raise FreshdeskTimeoutError(
                            f"Connection timed out for {operation_name} after {attempt + 1} attempts."
                        ) from exc

                    delay = calculate_jittered_backoff(attempt, self.base_delay, self.max_delay)
                    logger.warning(
                        "Timeout during %s: %s. Retrying in %.2fs (attempt %d/%d)",
                        operation_name,
                        str(exc),
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    attempt += 1
                    await asyncio.sleep(min(delay, max(0.1, deadline - time.time())))

                except httpx.NetworkError as exc:
                    if attempt >= self.max_retries:
                        raise FreshdeskAPIError(
                            f"Network error connecting to Freshdesk for {operation_name}: {exc}",
                            retryable=True,
                            details={"attempts": attempt + 1},
                        ) from exc

                    delay = calculate_jittered_backoff(attempt, self.base_delay, self.max_delay)
                    logger.warning(
                        "Network error during %s. Retrying in %.2fs (attempt %d/%d)",
                        operation_name,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    attempt += 1
                    await asyncio.sleep(min(delay, max(0.1, deadline - time.time())))

    def _handle_client_error(self, response: httpx.Response) -> None:
        """Parse non-retryable 4xx responses and raise specific exceptions."""
        status = response.status_code
        err_msg = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                err_msg = body.get("message") or body.get("description") or ""
        except Exception:
            err_msg = response.text[:200]

        if status == 401:
            raise FreshdeskAuthenticationError(
                message=f"Authentication failed (HTTP 401): {err_msg or 'Invalid or expired API key.'}",
                details={"status_code": 401},
            )
        if status == 403:
            raise FreshdeskPermissionError(
                message=f"Access forbidden (HTTP 403): {err_msg or 'Insufficient permissions.'}",
                details={"status_code": 403},
            )
        if status == 404:
            raise FreshdeskNotFoundError(
                message=f"Resource not found (HTTP 404): {err_msg or 'The requested resource does not exist.'}",
                details={"status_code": 404},
            )
        if status in (400, 422):
            raise FreshdeskValidationError(
                message=f"Validation failed (HTTP {status}): {err_msg or 'Invalid request parameters.'}",
                details={"status_code": status},
            )
        raise FreshdeskAPIError(
            message=f"Freshdesk client error HTTP {status}: {err_msg}",
            status_code=status,
            retryable=False,
        )
