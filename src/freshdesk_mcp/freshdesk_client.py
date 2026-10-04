"""Asynchronous HTTP client for Freshdesk REST API v2.

Handles HTTP Basic Authentication, connection pooling, read-only enforcement,
and resilient request dispatching via RetryPolicy.
"""

import logging
import time
from typing import Any

import httpx

from freshdesk_mcp.config import Settings
from freshdesk_mcp.exceptions import (
    FreshdeskAPIError,
    FreshdeskAuthenticationError,
    FreshdeskPermissionError,
)
from freshdesk_mcp.retry import RetryPolicy
from freshdesk_mcp.security import assert_read_only_method

logger = logging.getLogger("freshdesk_mcp.client")


class FreshdeskClient:
    """Async client interacting strictly via GET with Freshdesk REST API v2."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.base_url = settings.api_base_url
        self.retry_policy = RetryPolicy(
            max_retries=settings.freshdesk_max_retries,
            concurrency_limit=settings.freshdesk_concurrency_limit,
            total_timeout=settings.freshdesk_timeout * (settings.freshdesk_max_retries + 1),
        )

        # Freshdesk requires HTTP Basic Auth with API key as username and 'X' as password
        api_key_val = settings.freshdesk_api_key.get_secret_value()
        self._auth = (api_key_val, "X")

        self._headers = {
            "Accept": "application/json",
            "User-Agent": "Freshdesk-MCP-Connector/0.1.0",
        }

        # Internal or injected httpx client
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            auth=self._auth,
            headers=self._headers,
            timeout=httpx.Timeout(settings.freshdesk_timeout),
            follow_redirects=True,
        )
        self._owned_client = client is None

    async def aclose(self) -> None:
        """Close the underlying HTTP client session."""
        if self._owned_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "FreshdeskClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a read-only GET request against the Freshdesk API.

        Args:
            endpoint: Relative path (e.g. '/tickets' or '/tickets/123')
            params: Optional query parameters dictionary

        Returns:
            Parsed JSON object or list

        Raises:
            FreshdeskBaseError: On client, server, auth, rate limit, or network errors.
        """
        assert_read_only_method("GET")

        # Clean endpoint to ensure proper leading slash
        clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"

        # Clean params by filtering out None values
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        async def _dispatch() -> httpx.Response:
            return await self._client.get(clean_endpoint, params=clean_params)

        op_name = f"GET {clean_endpoint}"
        response = await self.retry_policy.execute(_dispatch, operation_name=op_name)

        try:
            return response.json()
        except Exception as exc:
            raise FreshdeskAPIError(
                f"Failed to parse JSON response from {op_name}.",
                status_code=response.status_code,
                retryable=False,
            ) from exc

    async def verify_credentials(self) -> tuple[bool, float, str | None]:
        """Safely test whether configured credentials can authenticate against Freshdesk.

        Returns:
            (is_valid, latency_ms, error_message_if_any)
        """
        start_time = time.perf_counter()
        try:
            # Query ticket fields with per_page=1 as a fast read-only probe
            await self.get("/ticket_fields", params={"per_page": 1})
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return True, latency_ms, None
        except FreshdeskAuthenticationError:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return False, latency_ms, "Authentication failed (HTTP 401): Invalid API key or domain."
        except FreshdeskPermissionError:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return (
                False,
                latency_ms,
                "Access forbidden (HTTP 403): User lacks ticket reading permissions.",
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning("Freshdesk credential verification failed: %s", exc)
            return False, latency_ms, f"Connectivity check failed: {type(exc).__name__}"
