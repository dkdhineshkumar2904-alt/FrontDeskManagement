"""Integration tests for MCP tool discovery, schemas, and read-only guarantees."""

import pytest

from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.server import create_mcp_server


@pytest.mark.asyncio
async def test_all_five_tools_registered(freshdesk_service: FreshdeskService) -> None:
    """Verify exactly the five required read-only tools are registered on the MCP server."""
    server = create_mcp_server(freshdesk_service)
    tools = await server.list_tools()

    tool_names = {tool.name for tool in tools}
    expected_tools = {
        "list_tickets",
        "get_ticket",
        "search_tickets",
        "get_ticket_conversations",
        "get_connector_health",
    }
    assert expected_tools.issubset(tool_names)
    assert len(tool_names) == 5


@pytest.mark.asyncio
async def test_tool_schemas_and_descriptions(freshdesk_service: FreshdeskService) -> None:
    """Verify tool descriptions and argument schemas are properly formed."""
    server = create_mcp_server(freshdesk_service)
    tools = await server.list_tools()
    tool_map = {tool.name: tool for tool in tools}

    # list_tickets
    list_tool = tool_map["list_tickets"]
    assert "READ-ONLY" in (list_tool.description or "")
    props = list_tool.input_schema.get("properties", {})
    assert "page" in props
    assert "per_page" in props
    assert "status" in props
    assert "priority" in props

    # get_ticket
    get_tool = tool_map["get_ticket"]
    assert "READ-ONLY" in (get_tool.description or "")
    assert "ticket_id" in get_tool.input_schema.get("properties", {})
    assert "ticket_id" in get_tool.input_schema.get("required", [])

    # search_tickets
    search_tool = tool_map["search_tickets"]
    assert "READ-ONLY" in (search_tool.description or "")
    assert "query" in search_tool.input_schema.get("properties", {})
    assert "query" in search_tool.input_schema.get("required", [])

    # get_ticket_conversations
    conv_tool = tool_map["get_ticket_conversations"]
    assert "ticket_id" in conv_tool.input_schema.get("properties", {})
    assert "ticket_id" in conv_tool.input_schema.get("required", [])

    # get_connector_health
    health_tool = tool_map["get_connector_health"]
    assert health_tool is not None


@pytest.mark.asyncio
async def test_read_only_guarantee_no_mutating_tools(freshdesk_service: FreshdeskService) -> None:
    """Verify NO mutating tools (create, update, delete, reply, close) are registered."""
    server = create_mcp_server(freshdesk_service)
    tools = await server.list_tools()
    tool_names = [tool.name.lower() for tool in tools]

    forbidden_keywords = [
        "create",
        "update",
        "delete",
        "close",
        "reply",
        "modify",
        "patch",
        "put",
        "post",
    ]
    for name in tool_names:
        for kw in forbidden_keywords:
            assert kw not in name, f"Prohibited mutation action '{kw}' found in tool name '{name}'"
