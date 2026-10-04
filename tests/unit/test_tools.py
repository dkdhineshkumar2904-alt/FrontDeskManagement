"""Unit tests for MCP tool functions."""

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from mcp.types import CallToolResult

from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.server import create_mcp_server


def _extract_dict(result: Any) -> dict[str, Any]:
    """Helper to assert CallToolResult and extract structured_content dictionary."""
    assert isinstance(result, CallToolResult)
    structured = result.structured_content
    assert isinstance(structured, dict)
    return structured


@pytest.mark.asyncio
@respx.mock
async def test_tool_list_tickets_success(
    freshdesk_service: FreshdeskService,
    raw_tickets_list: list[dict[str, Any]],
) -> None:
    """Verify list_tickets tool execution through server call_tool."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets").mock(
        return_value=httpx.Response(200, json=raw_tickets_list)
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("list_tickets", {"page": 1, "per_page": 20})

    assert isinstance(result, CallToolResult)
    assert not result.is_error
    structured = _extract_dict(result)
    assert structured["success"] is True
    assert len(structured["tickets"]) == 3
    assert structured["tickets"][0]["id"] == 101
    assert structured["tickets"][0]["status_name"] == "Open"
    assert "data_safety_notice" in structured


@pytest.mark.asyncio
@respx.mock
async def test_tool_list_tickets_status_filter(
    freshdesk_service: FreshdeskService,
    raw_tickets_list: list[dict[str, Any]],
) -> None:
    """Verify list_tickets tool filters by status code."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets").mock(
        return_value=httpx.Response(200, json=raw_tickets_list)
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("list_tickets", {"status": 2})

    structured = _extract_dict(result)
    assert structured["success"] is True
    # Only ticket 101 has status 2
    assert len(structured["tickets"]) == 1
    assert structured["tickets"][0]["id"] == 101


@pytest.mark.asyncio
async def test_tool_list_tickets_invalid_updated_since(
    freshdesk_service: FreshdeskService,
) -> None:
    """Verify invalid updated_since returns a safe error dictionary."""
    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("list_tickets", {"updated_since": "invalid-timestamp"})

    structured = _extract_dict(result)
    assert structured["success"] is False
    assert structured["error_code"] == "VALIDATION_ERROR"
    assert "Invalid updated_since format" in structured["message"]


@pytest.mark.asyncio
@respx.mock
async def test_tool_get_ticket_with_conversations(
    freshdesk_service: FreshdeskService,
    raw_ticket_data: dict[str, Any],
    raw_conversations_list: list[dict[str, Any]],
) -> None:
    """Verify get_ticket retrieves ticket and conversation thread when requested."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/101").mock(
        return_value=httpx.Response(200, json=raw_ticket_data)
    )
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/101/conversations").mock(
        return_value=httpx.Response(200, json=raw_conversations_list)
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_ticket", {"ticket_id": 101, "include_conversations": True})

    structured = _extract_dict(result)
    assert structured["success"] is True
    ticket = structured["ticket"]
    assert ticket["id"] == 101
    assert ticket["conversations"] is not None
    assert len(ticket["conversations"]) == 3
    assert ticket["conversations"][0]["id"] == 1001


@pytest.mark.asyncio
async def test_tool_get_ticket_invalid_id(freshdesk_service: FreshdeskService) -> None:
    """Verify non-positive ticket_id returns a validation error."""
    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_ticket", {"ticket_id": -5})

    structured = _extract_dict(result)
    assert structured["success"] is False
    assert structured["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@respx.mock
async def test_tool_search_tickets_success(
    freshdesk_service: FreshdeskService,
    raw_ticket_data: dict[str, Any],
) -> None:
    """Verify search_tickets invokes Freshdesk search API with proper formatting."""
    route = respx.get("https://testcorp.freshdesk.com/api/v2/search/tickets").mock(
        return_value=httpx.Response(200, json={"results": [raw_ticket_data], "total": 1})
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("search_tickets", {"query": "tag:'payment_failure'"})

    assert route.called
    structured = _extract_dict(result)
    assert structured["success"] is True
    assert len(structured["tickets"]) == 1
    assert structured["tickets"][0]["id"] == 101
    assert "search_summary" in structured


@pytest.mark.asyncio
@respx.mock
async def test_tool_get_conversations_success(
    freshdesk_service: FreshdeskService,
    raw_conversations_list: list[dict[str, Any]],
) -> None:
    """Verify get_ticket_conversations retrieves messages list."""
    respx.get("https://testcorp.freshdesk.com/api/v2/tickets/101/conversations").mock(
        return_value=httpx.Response(200, json=raw_conversations_list)
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_ticket_conversations", {"ticket_id": 101})

    structured = _extract_dict(result)
    assert structured["success"] is True
    assert len(structured["conversations"]) == 3
    assert structured["conversations"][0]["id"] == 1001


@pytest.mark.asyncio
@respx.mock
async def test_tool_get_connector_health(freshdesk_service: FreshdeskService) -> None:
    """Verify get_connector_health reports connectivity status and version."""
    respx.get("https://testcorp.freshdesk.com/api/v2/ticket_fields").mock(
        return_value=httpx.Response(200, json=[])
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_connector_health", {})

    structured = _extract_dict(result)
    assert structured["success"] is True
    assert structured["status"] == "healthy"
    assert structured["freshdesk_connectivity"] == "connected"
    assert structured["read_only_enforced"] is True
    assert structured["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_tool_unexpected_exceptions_handled(
    freshdesk_service: FreshdeskService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that unexpected system exceptions in service are caught and converted to safe INTERNAL_ERROR payloads."""
    # Patch service methods safely using monkeypatch
    monkeypatch.setattr(
        freshdesk_service, "list_tickets", AsyncMock(side_effect=RuntimeError("Unexpected crash"))
    )
    monkeypatch.setattr(
        freshdesk_service, "get_ticket", AsyncMock(side_effect=RuntimeError("Unexpected crash"))
    )
    monkeypatch.setattr(
        freshdesk_service, "search_tickets", AsyncMock(side_effect=RuntimeError("Unexpected crash"))
    )
    monkeypatch.setattr(
        freshdesk_service,
        "get_ticket_conversations",
        AsyncMock(side_effect=RuntimeError("Unexpected crash")),
    )
    monkeypatch.setattr(
        freshdesk_service, "get_health", AsyncMock(side_effect=RuntimeError("Unexpected crash"))
    )

    server = create_mcp_server(freshdesk_service)

    # 1. list_tickets
    res1 = _extract_dict(await server.call_tool("list_tickets", {}))
    assert res1["success"] is False
    assert res1["error_code"] == "INTERNAL_ERROR"

    # 2. get_ticket
    res2 = _extract_dict(await server.call_tool("get_ticket", {"ticket_id": 101}))
    assert res2["success"] is False
    assert res2["error_code"] == "INTERNAL_ERROR"

    # 3. search_tickets
    res3 = _extract_dict(await server.call_tool("search_tickets", {"query": "tag:'test'"}))
    assert res3["success"] is False
    assert res3["error_code"] == "INTERNAL_ERROR"

    # 4. get_ticket_conversations
    res4 = _extract_dict(await server.call_tool("get_ticket_conversations", {"ticket_id": 101}))
    assert res4["success"] is False
    assert res4["error_code"] == "INTERNAL_ERROR"

    # 5. get_connector_health
    res5 = _extract_dict(await server.call_tool("get_connector_health", {}))
    assert res5["success"] is False
    assert res5["error_code"] == "HEALTH_CHECK_FAILED"


@pytest.mark.asyncio
async def test_service_aclose(freshdesk_service: FreshdeskService) -> None:
    """Verify service resources can be closed gracefully."""
    await freshdesk_service.aclose()
