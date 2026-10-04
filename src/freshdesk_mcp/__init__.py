"""Freshdesk Model Context Protocol (MCP) Connector.

Provides standardized, read-only access to Freshdesk support tickets,
conversations, and search for AI agents.
"""

from freshdesk_mcp.config import Settings, load_settings
from freshdesk_mcp.exceptions import (
    FreshdeskAPIError,
    FreshdeskAuthenticationError,
    FreshdeskBaseError,
    FreshdeskConfigurationError,
    FreshdeskNotFoundError,
    FreshdeskPermissionError,
    FreshdeskRateLimitError,
    FreshdeskTimeoutError,
    FreshdeskValidationError,
)
from freshdesk_mcp.freshdesk_client import FreshdeskClient
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.server import create_mcp_server

__version__ = "0.1.0"

__all__ = [
    "FreshdeskAPIError",
    "FreshdeskAuthenticationError",
    "FreshdeskBaseError",
    "FreshdeskClient",
    "FreshdeskConfigurationError",
    "FreshdeskNotFoundError",
    "FreshdeskPermissionError",
    "FreshdeskRateLimitError",
    "FreshdeskService",
    "FreshdeskTimeoutError",
    "FreshdeskValidationError",
    "Settings",
    "__version__",
    "create_mcp_server",
    "load_settings",
]
