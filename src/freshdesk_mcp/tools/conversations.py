"""Conversations MCP tool: get_ticket_conversations.

Provides read-only access to customer and agent replies and internal notes.
"""

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.exceptions import FreshdeskBaseError
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.schemas import ErrorResponse

logger = logging.getLogger("freshdesk_mcp.tools.conversations")


def register_conversation_tools(server: MCPServer, service: FreshdeskService) -> None:
    """Register get_ticket_conversations tool on the MCP server."""

    @server.tool(
        name="get_ticket_conversations",
        description=(
            "Retrieve conversation messages, replies, and notes associated with a specific Freshdesk ticket. "
            "Use this tool to read customer messages, agent replies, and internal notes for a case.\n"
            "Arguments:\n"
            "- ticket_id (int, required, min 1): The unique positive integer ID of the Freshdesk ticket.\n"
            "- page (int, default 1, min 1): 1-indexed page number.\n"
            "- per_page (int, default 20, min 1, max 100): Number of conversation entries per page.\n"
            "Guarantees: READ-ONLY. Never sends replies, notes, or messages to Freshdesk."
        ),
    )
    async def get_ticket_conversations(
        ticket_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        try:
            res = await service.get_ticket_conversations(
                ticket_id=ticket_id,
                page=page,
                per_page=per_page,
            )
            return res.model_dump()
        except FreshdeskBaseError as exc:
            logger.warning(
                "Freshdesk error in get_ticket_conversations (%d): %s", ticket_id, exc.message
            )
            return exc.to_tool_error_dict()
        except Exception as exc:
            logger.exception(
                "Unexpected error in get_ticket_conversations (%d): %s", ticket_id, exc
            )
            return ErrorResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message=f"An unexpected error occurred while retrieving conversations for ticket {ticket_id}.",
                retryable=False,
            ).model_dump()
