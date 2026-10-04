"""End-to-end integration tests with mocked Freshdesk API interactions."""

from typing import Any

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
async def test_complete_agent_triage_flow(
    freshdesk_service: FreshdeskService,
    raw_tickets_list: list[dict[str, Any]],
    raw_ticket_data: dict[str, Any],
    raw_conversations_list: list[dict[str, Any]],
) -> None:
    """Simulate a full agent workflow:

    1. List open tickets.
    2. Retrieve details for high-priority ticket #101.
    3. Retrieve conversation replies for ticket #101.
    4. Search related tickets by tag 'payment_failure'.
    5. Perform connector health check.
    """
    base_url = "https://testcorp.freshdesk.com/api/v2"

    respx.get(f"{base_url}/tickets").mock(return_value=httpx.Response(200, json=raw_tickets_list))
    respx.get(f"{base_url}/tickets/101").mock(
        return_value=httpx.Response(200, json=raw_ticket_data)
    )
    respx.get(f"{base_url}/tickets/101/conversations").mock(
        return_value=httpx.Response(200, json=raw_conversations_list)
    )
    respx.get(f"{base_url}/search/tickets").mock(
        return_value=httpx.Response(200, json={"results": [raw_ticket_data], "total": 1})
    )
    respx.get(f"{base_url}/ticket_fields").mock(return_value=httpx.Response(200, json=[]))

    server = create_mcp_server(freshdesk_service)

    # Step 1: List tickets
    step1 = await server.call_tool("list_tickets", {"page": 1, "per_page": 20})
    tickets = _extract_dict(step1)["tickets"]
    assert len(tickets) == 3

    # Step 2: Get specific ticket #101
    step2 = await server.call_tool("get_ticket", {"ticket_id": 101, "include_conversations": True})
    ticket = _extract_dict(step2)["ticket"]
    assert ticket["id"] == 101
    assert ticket["status_name"] == "Open"
    assert ticket["priority_name"] == "High"
    assert len(ticket["conversations"]) == 3

    # Step 3: Get conversations directly
    step3 = await server.call_tool("get_ticket_conversations", {"ticket_id": 101})
    convs = _extract_dict(step3)["conversations"]
    assert len(convs) == 3

    # Step 4: Search tickets
    step4 = await server.call_tool("search_tickets", {"query": "tag:'payment_failure'"})
    search_res = _extract_dict(step4)["tickets"]
    assert len(search_res) == 1
    assert search_res[0]["id"] == 101

    # Step 5: Check health
    step5 = await server.call_tool("get_connector_health", {})
    health = _extract_dict(step5)
    assert health["status"] == "healthy"
    assert health["freshdesk_connectivity"] == "connected"


@pytest.mark.asyncio
@respx.mock
async def test_agent_rate_limit_recovery(
    freshdesk_service: FreshdeskService,
    raw_ticket_data: dict[str, Any],
) -> None:
    """Verify tool execution transparently recovers from transient 429 rate limit."""
    base_url = "https://testcorp.freshdesk.com/api/v2"

    route = respx.get(f"{base_url}/tickets/101")
    route.side_effect = [
        httpx.Response(
            429, headers={"Retry-After": "0.01"}, json={"message": "Rate limit exceeded"}
        ),
        httpx.Response(200, json=raw_ticket_data),
    ]

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_ticket", {"ticket_id": 101})

    structured = _extract_dict(result)
    assert structured["success"] is True
    assert structured["ticket"]["id"] == 101
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_agent_401_authentication_error(
    freshdesk_service: FreshdeskService,
) -> None:
    """Verify 401 error is converted into clean structured error payload."""
    base_url = "https://testcorp.freshdesk.com/api/v2"
    respx.get(f"{base_url}/tickets").mock(
        return_value=httpx.Response(
            401, json={"message": "You have to be logged in to perform this action."}
        )
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("list_tickets", {})

    structured = _extract_dict(result)
    assert structured["success"] is False
    assert structured["error_code"] == "AUTHENTICATION_FAILED"
    assert structured["retryable"] is False


@pytest.mark.asyncio
@respx.mock
async def test_agent_404_not_found_error(
    freshdesk_service: FreshdeskService,
) -> None:
    """Verify 404 error is converted into clean structured error payload."""
    base_url = "https://testcorp.freshdesk.com/api/v2"
    respx.get(f"{base_url}/tickets/99999").mock(
        return_value=httpx.Response(404, json={"message": "Record not found"})
    )

    server = create_mcp_server(freshdesk_service)
    result = await server.call_tool("get_ticket", {"ticket_id": 99999})

    structured = _extract_dict(result)
    assert structured["success"] is False
    assert structured["error_code"] == "RESOURCE_NOT_FOUND"
    assert structured["retryable"] is False
