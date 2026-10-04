"""Unit tests for server entry point, lifecycle, and CLI parsing."""

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from freshdesk_mcp.config import Settings
from freshdesk_mcp.freshdesk_service import FreshdeskService
from freshdesk_mcp.server import cli, create_mcp_server, run_server


def test_create_mcp_server(freshdesk_service: FreshdeskService) -> None:
    """Verify MCPServer instance is created with expected name and version."""
    server = create_mcp_server(freshdesk_service)
    assert server.name == "freshdesk-mcp-connector"
    assert server.version == "0.1.0"


@pytest.mark.asyncio
async def test_run_server_stdio(mock_settings: Settings) -> None:
    """Verify run_server calls run_stdio_async when mcp_transport is stdio."""
    mock_settings.mcp_transport = "stdio"

    with patch("freshdesk_mcp.server.create_mcp_server") as mock_create:
        mock_mcp = AsyncMock()
        mock_mcp.run_stdio_async = AsyncMock(return_value=None)
        mock_create.return_value = mock_mcp

        await run_server(mock_settings)
        mock_mcp.run_stdio_async.assert_called_once()


@pytest.mark.asyncio
async def test_run_server_streamable_http(mock_settings: Settings) -> None:
    """Verify run_server calls run_streamable_http_async when transport is streamable-http."""
    mock_settings.mcp_transport = "streamable-http"
    mock_settings.mcp_host = "0.0.0.0"
    mock_settings.mcp_port = 8080

    with patch("freshdesk_mcp.server.create_mcp_server") as mock_create:
        mock_mcp = AsyncMock()
        mock_mcp.run_streamable_http_async = AsyncMock(return_value=None)
        mock_create.return_value = mock_mcp

        await run_server(mock_settings)
        mock_mcp.run_streamable_http_async.assert_called_once_with(
            host="0.0.0.0",
            port=8080,
            streamable_http_path="/mcp",
        )


@pytest.mark.asyncio
async def test_run_server_handles_cancelled_gracefully(mock_settings: Settings) -> None:
    """Verify CancelledError or KeyboardInterrupt triggers graceful cleanup."""
    with patch("freshdesk_mcp.server.create_mcp_server") as mock_create:
        mock_mcp = AsyncMock()
        mock_mcp.run_stdio_async = AsyncMock(side_effect=asyncio.CancelledError())
        mock_create.return_value = mock_mcp

        # Should handle CancelledError without re-raising
        await run_server(mock_settings)


def test_cli_argument_overrides(monkeypatch: pytest.MonkeyPatch, mock_settings: Settings) -> None:
    """Verify CLI flags override settings properly."""
    monkeypatch.setattr("freshdesk_mcp.server.load_settings", lambda: mock_settings)

    with patch("freshdesk_mcp.server.asyncio.run") as mock_run:
        test_argv = [
            "freshdesk-mcp",
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9090",
            "--log-level",
            "DEBUG",
        ]
        monkeypatch.setattr(sys, "argv", test_argv)
        cli()

        assert mock_settings.mcp_transport == "streamable-http"
        assert mock_settings.mcp_host == "0.0.0.0"
        assert mock_settings.mcp_port == 9090
        assert mock_settings.log_level == "DEBUG"
        mock_run.assert_called_once()


def test_cli_config_error_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI exits cleanly with error code when configuration cannot be loaded."""

    def mock_fail() -> Settings:
        raise ValueError("Missing env")

    monkeypatch.setattr("freshdesk_mcp.server.load_settings", mock_fail)
    monkeypatch.setattr(sys, "argv", ["freshdesk-mcp"])

    with pytest.raises(SystemExit) as exc:
        cli()
    assert exc.value.code == 1
