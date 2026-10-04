"""Health check MCP tool: get_connector_health.

Provides diagnostic health status, connectivity verification, and round-trip latency.
"""

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.schemas import ErrorResponse

logger = logging.getLogger("freshdesk_mcp.tools.health")


def register_health_tools(server: MCPServer, service: FreshdeskService) -> None:
    """Register get_connector_health tool on the MCP server."""

    @server.tool(
        name="get_connector_health",
        description=(
            "Check the operational health and external Freshdesk API connectivity of this MCP connector. "
            "Returns connector readiness, Freshdesk API ping status, round-trip latency, transport type, and version. "
            "Safe diagnostic tool that never exposes credentials or sensitive data.\n"
            "Guarantees: READ-ONLY."
        ),
    )
    async def get_connector_health() -> dict[str, Any]:
        try:
            res = await service.get_health()
            return res.model_dump()
        except Exception as exc:
            logger.exception("Unexpected error during health check: %s", exc)
            return ErrorResponse(
                success=False,
                error_code="HEALTH_CHECK_FAILED",
                message="Health check encountered an internal failure.",
                retryable=True,
            ).model_dump()
