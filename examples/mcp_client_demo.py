"""Runnable demonstration script for Freshdesk MCP Connector.

Demonstrates how an AI Agent or MCP Client discovers tools, retrieves tickets,
searches for payment issues, and inspects conversation threads.

Can be run locally without real credentials using mocked Freshdesk responses.
Usage:
    python examples/mcp_client_demo.py
"""

import asyncio
import json
from typing import Any

import httpx
import respx

from freshdesk_mcp.config import Settings
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.server import create_mcp_server


def pretty_print(title: str, data: Any) -> None:
    """Helper to display formatted output."""
    print(f"\n{'=' * 70}\n[DEMO] {title}\n{'=' * 70}")
    print(json.dumps(data, indent=2))


async def run_agent_demonstration() -> None:
    """Run simulated agent workflow with the Freshdesk MCP Connector."""
    print("\nStarting Freshdesk MCP Connector Agent Demonstration...")

    # 1. Initialize configuration and service
    settings = Settings(
        FRESHDESK_DOMAIN="razorpay-merchant",
        FRESHDESK_API_KEY="demo_secret_api_key_for_testing",  # type: ignore[arg-type]
        FRESHDESK_TIMEOUT=5.0,
        FRESHDESK_MAX_RETRIES=2,
        FRESHDESK_MAX_PAGES=3,
        MCP_TRANSPORT="stdio",
        LOG_LEVEL="INFO",
    )

    # Mock external Freshdesk endpoints to allow turnkey execution without live API credentials
    base_url = "https://razorpay-merchant.freshdesk.com/api/v2"

    mock_tickets = [
        {
            "id": 90125,
            "subject": "Payment failure on Order #10029 - Gateway Timeout",
            "description_text": "Merchant reports customers seeing 504 Gateway Timeout during checkout on HDFC Netbanking.",
            "status": 2,  # Open
            "priority": 3,  # High
            "type": "Incident",
            "requester_id": 401,
            "responder_id": 801,
            "group_id": 12,
            "created_at": "2026-10-04T08:00:00Z",
            "updated_at": "2026-10-04T09:30:00Z",
            "due_by": "2026-10-04T12:00:00Z",
            "tags": ["payment_failure", "netbanking", "hdfc"],
            "custom_fields": {"cf_merchant_id": "merch_razorpay_992"},
        },
        {
            "id": 90126,
            "subject": "Webhook delivery failure for captured payment",
            "description_text": "Merchant server received payment.authorized but missing payment.captured webhook.",
            "status": 2,  # Open
            "priority": 3,  # High
            "type": "Incident",
            "requester_id": 402,
            "responder_id": 802,
            "group_id": 12,
            "created_at": "2026-10-04T08:15:00Z",
            "updated_at": "2026-10-04T09:45:00Z",
            "due_by": "2026-10-04T14:00:00Z",
            "tags": ["webhook", "payment_failure"],
            "custom_fields": {"cf_merchant_id": "merch_razorpay_118"},
        },
    ]

    mock_conversations = [
        {
            "id": 5001,
            "ticket_id": 90125,
            "body_text": "Our merchants are reporting that HDFC transactions are failing with status 'Timeout from Bank'.",
            "user_id": 401,
            "incoming": True,
            "private": False,
            "created_at": "2026-10-04T08:00:00Z",
            "updated_at": "2026-10-04T08:00:00Z",
        },
        {
            "id": 5002,
            "ticket_id": 90125,
            "body_text": "Bank partner confirmed temporary maintenance on the HDFC netbanking gateway between 08:00-08:45 UTC. Services restored.",
            "user_id": 801,
            "incoming": False,
            "private": True,
            "created_at": "2026-10-04T09:00:00Z",
            "updated_at": "2026-10-04T09:00:00Z",
        },
    ]

    with respx.mock:
        respx.get(f"{base_url}/ticket_fields").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{base_url}/tickets").mock(return_value=httpx.Response(200, json=mock_tickets))
        respx.get(f"{base_url}/tickets/90125").mock(
            return_value=httpx.Response(200, json=mock_tickets[0])
        )
        respx.get(f"{base_url}/tickets/90125/conversations").mock(
            return_value=httpx.Response(200, json=mock_conversations)
        )
        respx.get(f"{base_url}/search/tickets").mock(
            return_value=httpx.Response(200, json={"results": [mock_tickets[0]], "total": 1})
        )
        respx.get(f"{base_url}/tickets/99999").mock(
            return_value=httpx.Response(404, json={"message": "Record not found"})
        )

        service = FreshdeskService(settings)
        server = create_mcp_server(service)

        # -------------------------------------------------------------
        # STEP 1: Tool Discovery
        # -------------------------------------------------------------
        tools = await server.list_tools()
        pretty_print(
            "Step 1: MCP Tool Discovery",
            [{"name": t.name, "description": (t.description or "").split("\n")[0]} for t in tools],
        )

        # -------------------------------------------------------------
        # STEP 2: Diagnostic Health Check
        # -------------------------------------------------------------
        health_res = await server.call_tool("get_connector_health", {})
        pretty_print("Step 2: Connector Health Check", health_res.structured_content)

        # -------------------------------------------------------------
        # STEP 3: List Recent Open Tickets
        # -------------------------------------------------------------
        list_res = await server.call_tool("list_tickets", {"page": 1, "per_page": 10, "status": 2})
        pretty_print("Step 3: List Open Support Tickets (status=2)", list_res.structured_content)

        # -------------------------------------------------------------
        # STEP 4: Search for Specific Failure Keywords
        # -------------------------------------------------------------
        search_res = await server.call_tool(
            "search_tickets", {"query": "tag:'payment_failure' AND priority:3"}
        )
        pretty_print(
            "Step 4: Search Tickets (query=\"tag:'payment_failure' AND priority:3\")",
            search_res.structured_content,
        )

        # -------------------------------------------------------------
        # STEP 5: Deep-Dive Ticket Details & Conversation History
        # -------------------------------------------------------------
        ticket_res = await server.call_tool(
            "get_ticket", {"ticket_id": 90125, "include_conversations": True}
        )
        pretty_print(
            "Step 5: Get Ticket Details & Conversations (ID: 90125)",
            ticket_res.structured_content,
        )

        # -------------------------------------------------------------
        # STEP 6: Defensive Error Handling (Resource Not Found)
        # -------------------------------------------------------------
        err_res = await server.call_tool("get_ticket", {"ticket_id": 99999})
        pretty_print(
            "Step 6: Defensive Error Handling (Nonexistent ID)", err_res.structured_content
        )

        # -------------------------------------------------------------
        # STEP 7: Simulated AI Agent Synthesis
        # -------------------------------------------------------------
        print(f"\n{'=' * 70}\n[DEMO] Step 7: Final AI Agent Synthesis\n{'=' * 70}")
        agent_summary = (
            "Agent Resolution Summary:\n"
            "-------------------------\n"
            "• Incident: Ticket #90125 ('Payment failure on Order #10029 - Gateway Timeout')\n"
            "• Severity: High (Priority 3), Status: Open (Status 2)\n"
            "• Merchant ID: merch_razorpay_992\n"
            "• Cause: Temporary bank partner maintenance on HDFC Netbanking (08:00-08:45 UTC).\n"
            "• Internal Note: Services have been restored by the bank partner.\n"
            "• Recommendation: Inform merchant that HDFC Netbanking is back online; suggest verifying transactions."
        )
        print(agent_summary)
        print(f"\n{'=' * 70}\nDemonstration completed successfully.\n{'=' * 70}\n")

        await service.aclose()


if __name__ == "__main__":
    asyncio.run(run_agent_demonstration())
