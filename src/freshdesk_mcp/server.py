"""Main server entrypoint for Freshdesk Model Context Protocol (MCP) Connector.

Supports both stdio and Streamable HTTP transports with lifecycle management,
graceful shutdown, and safe diagnostic logging.
"""

import argparse
import asyncio
import contextlib
import logging
import sys

from mcp.server.mcpserver import MCPServer

from freshdesk_mcp.config import Settings, load_settings
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.logging_config import setup_logging
from freshdesk_mcp.tools import register_all_tools

logger = logging.getLogger("freshdesk_mcp.server")


def create_mcp_server(service: FreshdeskService) -> MCPServer:
    """Create and configure the MCPServer instance with registered tools."""
    server = MCPServer(
        name="freshdesk-mcp-connector",
        version="0.1.0",
        description="Production-grade read-only Freshdesk MCP Connector for AI agents",
    )
    register_all_tools(server, service)
    return server


async def run_server(settings: Settings) -> None:
    """Start the MCP server with the configured transport and graceful resource cleanup."""
    log = setup_logging(log_level=settings.log_level, transport=settings.mcp_transport)
    log.info("Starting Freshdesk MCP Connector v0.1.0 (transport: %s)", settings.mcp_transport)

    service = FreshdeskService(settings)
    server = create_mcp_server(service)

    try:
        if settings.mcp_transport == "stdio":
            log.info(
                "Listening on stdio transport. Standard input/output reserved for MCP protocol."
            )
            await server.run_stdio_async()
        elif settings.mcp_transport == "streamable-http":
            if settings.mcp_host in ("0.0.0.0", "::"):
                log.warning(
                    "SECURITY NOTICE: Streamable HTTP transport bound to %s:%d. "
                    "Ensure TLS termination and authentication are enforced at reverse proxy/firewall.",
                    settings.mcp_host,
                    settings.mcp_port,
                )
            log.info(
                "Listening on Streamable HTTP transport at http://%s:%d%s",
                settings.mcp_host,
                settings.mcp_port,
                settings.mcp_path,
            )
            await server.run_streamable_http_async(
                host=settings.mcp_host,
                port=settings.mcp_port,
                streamable_http_path=settings.mcp_path,
            )
        else:
            raise ValueError(f"Unsupported MCP_TRANSPORT: {settings.mcp_transport}")
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Shutdown signal received. Performing graceful shutdown...")
    finally:
        log.info("Closing HTTP client connections and freeing resources...")
        await service.aclose()
        log.info("Freshdesk MCP Connector stopped successfully.")


def cli() -> None:
    """Command-line entry point with optional argument overrides."""
    parser = argparse.ArgumentParser(
        prog="freshdesk-mcp",
        description="Freshdesk Model Context Protocol (MCP) Connector for AI Agents",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=None,
        help="MCP transport mode (overrides MCP_TRANSPORT env var)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host for streamable-http transport (overrides MCP_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for streamable-http transport (overrides MCP_PORT env var)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Logging level (overrides LOG_LEVEL env var)",
    )

    args = parser.parse_args()

    try:
        settings = load_settings()
    except Exception as exc:
        # Output directly to stderr to avoid contaminating stdout in stdio mode
        sys.stderr.write(f"Configuration Error: {exc}\n")
        sys.stderr.write("Please check your .env file or environment variables.\n")
        sys.exit(1)

    # Apply CLI overrides if specified
    if args.transport:
        settings.mcp_transport = args.transport
    if args.host:
        settings.mcp_host = args.host
    if args.port:
        settings.mcp_port = args.port
    if args.log_level:
        settings.log_level = args.log_level

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_server(settings))


if __name__ == "__main__":
    cli()
