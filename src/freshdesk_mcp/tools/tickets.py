"""Tickets MCP tools: list_tickets and get_ticket.

Provides read-only access to paginated ticket listings and individual ticket details.
"""

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.exceptions import FreshdeskBaseError
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.schemas import ErrorResponse

logger = logging.getLogger("freshdesk_mcp.tools.tickets")


def register_ticket_tools(server: MCPServer, service: FreshdeskService) -> None:
    """Register list_tickets and get_ticket tools on the MCP server."""

    @server.tool(
        name="list_tickets",
        description=(
            "Retrieve a paginated list of Freshdesk support tickets. "
            "Use this tool to explore recent tickets, filter by requester or status, or monitor support volume. "
            "Arguments:\n"
            "- page (int, default 1, min 1): 1-indexed page number.\n"
            "- per_page (int, default 20, min 1, max 100): number of tickets per page.\n"
            "- status (int, optional): Filter by status code (2=Open, 3=Pending, 4=Resolved, 5=Closed).\n"
            "- priority (int, optional): Filter by priority code (1=Low, 2=Medium, 3=High, 4=Urgent).\n"
            "- requester_id (int, optional): Filter tickets by contact ID of the customer.\n"
            "- updated_since (str, optional): ISO 8601 UTC timestamp (e.g. '2026-09-01T10:00:00Z').\n"
            "Guarantees: READ-ONLY. Never modifies or creates tickets."
        ),
    )
    async def list_tickets(
        page: int = 1,
        per_page: int = 20,
        status: int | None = None,
        priority: int | None = None,
        requester_id: int | None = None,
        updated_since: str | None = None,
    ) -> dict[str, Any]:
        try:
            res = await service.list_tickets(
                page=page,
                per_page=per_page,
                status=status,
                priority=priority,
                requester_id=requester_id,
                updated_since=updated_since,
            )
            return res.model_dump()
        except FreshdeskBaseError as exc:
            logger.warning("Freshdesk error in list_tickets: %s", exc.message)
            return exc.to_tool_error_dict()
        except Exception as exc:
            logger.exception("Unexpected error in list_tickets: %s", exc)
            return ErrorResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred while listing tickets.",
                retryable=False,
            ).model_dump()

    @server.tool(
        name="get_ticket",
        description=(
            "Retrieve complete details for an individual Freshdesk ticket by its ID. "
            "Use this tool when you need deep context on a specific issue, custom fields, tags, or conversation history. "
            "Arguments:\n"
            "- ticket_id (int, required, min 1): The unique positive integer ID of the Freshdesk ticket.\n"
            "- include_conversations (bool, default false): If true, fetches the conversation thread (replies and notes).\n"
            "Guarantees: READ-ONLY. Never alters ticket status, assignments, or contents."
        ),
    )
    async def get_ticket(
        ticket_id: int,
        include_conversations: bool = False,
    ) -> dict[str, Any]:
        try:
            res = await service.get_ticket(
                ticket_id=ticket_id,
                include_conversations=include_conversations,
            )
            return res.model_dump()
        except FreshdeskBaseError as exc:
            logger.warning("Freshdesk error in get_ticket (%d): %s", ticket_id, exc.message)
            return exc.to_tool_error_dict()
        except Exception as exc:
            logger.exception("Unexpected error in get_ticket (%d): %s", ticket_id, exc)
            return ErrorResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message=f"An unexpected error occurred while retrieving ticket {ticket_id}.",
                retryable=False,
            ).model_dump()
