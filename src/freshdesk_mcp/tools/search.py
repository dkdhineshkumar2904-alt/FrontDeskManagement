"""Search MCP tool: search_tickets.

Executes structured searches against the Freshdesk Search API v2.
"""

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.exceptions import FreshdeskBaseError
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.schemas import ErrorResponse

logger = logging.getLogger("freshdesk_mcp.tools.search")


def register_search_tools(server: MCPServer, service: FreshdeskService) -> None:
    """Register search_tickets tool on the MCP server."""

    @server.tool(
        name="search_tickets",
        description=(
            "Search Freshdesk support tickets using Freshdesk Search API v2 syntax. "
            "Use this tool when you need to find tickets matching specific criteria, such as "
            "keywords in subject/description, specific tags, status combinations, or date ranges.\n"
            "Arguments:\n"
            "- query (str, required, max 500 chars): Freshdesk query string. "
            "Examples:\n"
            '  * "status:2 AND priority:3" (Open Urgent tickets)\n'
            "  * \"tag:'payment_failure'\" (Tickets tagged payment_failure)\n"
            "  * \"created_at:>'2026-01-01'\" (Tickets created after date)\n"
            "- page (int, default 1, min 1): 1-indexed page number.\n"
            "- per_page (int, default 20, max 30): Results per page (Freshdesk API maximum is 30 for search).\n"
            "Important Limitations:\n"
            "- Search results are capped at 300 tickets maximum by Freshdesk.\n"
            "- Newly created or modified tickets have an indexing latency of approximately 5 minutes.\n"
            "Guarantees: READ-ONLY. Never updates or modifies tickets."
        ),
    )
    async def search_tickets(
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        try:
            res = await service.search_tickets(
                query=query,
                page=page,
                per_page=per_page,
            )
            return res.model_dump()
        except FreshdeskBaseError as exc:
            logger.warning("Freshdesk error in search_tickets ('%s'): %s", query, exc.message)
            return exc.to_tool_error_dict()
        except Exception as exc:
            logger.exception("Unexpected error in search_tickets ('%s'): %s", query, exc)
            return ErrorResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred while searching tickets.",
                retryable=False,
            ).model_dump()
