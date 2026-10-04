"""Unit tests for Freshdesk asynchronous HTTP client."""

import base64

import httpx
import pytest
import respx

from freshdesk_mcp.config import Settings
from freshdesk_mcp.exceptions import (
    FreshdeskAPIError,
    FreshdeskNotFoundError,
)
from freshdesk_mcp.freshdesk_client import FreshdeskClient


@pytest.mark.asyncio
@respx.mock
async def test_client_authentication_header(mock_settings: Settings) -> None:
    """Verify HTTP Basic Authentication header contains base64(api_key:X)."""
    expected_token = base64.b64encode(b"test_secret_api_key_valid:X").decode("ascii")
    expected_auth = f"Basic {expected_token}"

    route = respx.get("https://testcorp.freshdesk.com/api/v2/tickets").mock(
        return_value=httpx.Response(200, json=[])
    )

    async with FreshdeskClient(mock_settings) as client:
        await client.get("/tickets")

    assert route.called
    last_req = route.calls.last.request
    assert last_req.headers.get("Authorization") == expected_auth
    assert last_req.headers.get("Accept") == "application/json"


@pytest.mark.asyncio
@respx.mock
async def test_client_get_success(mock_settings: Settings) -> None:
    """Verify successful GET returns parsed JSON body."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/101").mock(
        return_value=httpx.Response(200, json={"id": 101, "subject": "Test ticket"})
    )

    async with FreshdeskClient(mock_settings) as client:
        data = await client.get("/tickets/101")

    assert data["id"] == 101
    assert data["subject"] == "Test ticket"


@pytest.mark.asyncio
@respx.mock
async def test_client_get_handles_none_params(mock_settings: Settings) -> None:
    """Verify params with None values are excluded from the request URL."""
    route = respx.get("https://testcorp.freshdesk.com/api/v2/tickets").mock(
        return_value=httpx.Response(200, json=[])
    )

    async with FreshdeskClient(mock_settings) as client:
        await client.get("/tickets", params={"page": 1, "requester_id": None})

    assert route.called
    url_str = str(route.calls.last.request.url)
    assert "page=1" in url_str
    assert "requester_id" not in url_str


@pytest.mark.asyncio
@respx.mock
async def test_client_handles_invalid_json(mock_settings: Settings) -> None:
    """Verify non-JSON response raises FreshdeskAPIError."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/101").mock(
        return_value=httpx.Response(200, text="<!DOCTYPE html><html>Gateway</html>")
    )

    async with FreshdeskClient(mock_settings) as client:
        with pytest.raises(FreshdeskAPIError) as exc_info:
            await client.get("/tickets/101")
    assert "Failed to parse JSON" in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_client_handles_404_not_found(mock_settings: Settings) -> None:
    """Verify 404 response raises FreshdeskNotFoundError."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/999").mock(
        return_value=httpx.Response(404, json={"message": "Record not found"})
    )

    async with FreshdeskClient(mock_settings) as client:
        with pytest.raises(FreshdeskNotFoundError):
            await client.get("/tickets/999")


@pytest.mark.asyncio
@respx.mock
async def test_verify_credentials_success(mock_settings: Settings) -> None:
    """Verify verify_credentials reports success when probe succeeds."""
    respx.get("https://testcorp.freshdesk.com/api/v2/ticket_fields").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "status"}])
    )

    async with FreshdeskClient(mock_settings) as client:
        is_valid, latency, error = await client.verify_credentials()

    assert is_valid is True
    assert latency >= 0.0
    assert error is None


@pytest.mark.asyncio
@respx.mock
async def test_verify_credentials_unauthorized(mock_settings: Settings) -> None:
    """Verify verify_credentials handles 401 without crashing."""
    respx.get("https://testcorp.freshdesk.com/api/v2/ticket_fields").mock(
        return_value=httpx.Response(401, json={"message": "Invalid credentials"})
    )

    async with FreshdeskClient(mock_settings) as client:
        is_valid, _latency, error = await client.verify_credentials()

    assert is_valid is False
    assert error is not None
    assert "Authentication failed" in error


@pytest.mark.asyncio
@respx.mock
async def test_verify_credentials_forbidden(mock_settings: Settings) -> None:
    """Verify verify_credentials handles 403."""
    respx.get("https://testcorp.freshdesk.com/api/v2/ticket_fields").mock(
        return_value=httpx.Response(403, json={"message": "Access denied"})
    )

    async with FreshdeskClient(mock_settings) as client:
        is_valid, _latency, error = await client.verify_credentials()

    assert is_valid is False
    assert error is not None
    assert "Access forbidden" in error
