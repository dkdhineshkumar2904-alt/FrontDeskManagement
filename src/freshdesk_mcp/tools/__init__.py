"""MCP tools package for Freshdesk connector."""

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.tools.conversations import register_conversation_tools
from freshdesk_mcp.tools.health import register_health_tools
from freshdesk_mcp.tools.search import register_search_tools
from freshdesk_mcp.tools.tickets import register_ticket_tools


def register_all_tools(server: MCPServer, service: FreshdeskService) -> None:
    """Register all 5 read-only MCP tools onto the given MCPServer instance."""
    register_ticket_tools(server, service)
    register_search_tools(server, service)
    register_conversation_tools(server, service)
    register_health_tools(server, service)


__all__ = [
    "register_all_tools",
    "register_conversation_tools",
    "register_health_tools",
    "register_search_tools",
    "register_ticket_tools",
]
