"""Configuration management for Freshdesk MCP Connector.

Loads and validates settings from environment variables with safe defaults
and strict credential safeguards.
"""

import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from freshdesk_mcp.exceptions import FreshdeskConfigurationError

# RFC 1123 DNS label: lowercase alphanumeric characters and hyphens, 1-63 chars
_DOMAIN_LABEL_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")

_PLACEHOLDER_KEYS = {
    "your_freshdesk_api_key_here",
    "your_api_key_here",
    "placeholder",
    "secret",
    "changeme",
    "test_key",
}


class Settings(BaseSettings):
    """Strongly validated application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    freshdesk_domain: str = Field(
        ...,
        alias="FRESHDESK_DOMAIN",
        description="Freshdesk subdomain or full domain (e.g., 'company' or 'company.freshdesk.com')",
    )

    freshdesk_api_key: SecretStr = Field(
        ...,
        alias="FRESHDESK_API_KEY",
        description="Freshdesk API key for HTTP Basic Authentication",
    )

    freshdesk_timeout: float = Field(
        default=15.0,
        alias="FRESHDESK_TIMEOUT",
        ge=1.0,
        le=120.0,
        description="HTTP request timeout in seconds",
    )

    freshdesk_max_retries: int = Field(
        default=3,
        alias="FRESHDESK_MAX_RETRIES",
        ge=0,
        le=10,
        description="Maximum retry attempts for transient errors",
    )

    freshdesk_max_pages: int = Field(
        default=5,
        alias="FRESHDESK_MAX_PAGES",
        ge=1,
        le=50,
        description="Maximum pagination depth per tool call",
    )

    freshdesk_concurrency_limit: int = Field(
        default=5,
        alias="FRESHDESK_CONCURRENCY_LIMIT",
        ge=1,
        le=20,
        description="Maximum concurrent outgoing requests to Freshdesk",
    )

    mcp_transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        alias="MCP_TRANSPORT",
        description="MCP transport mode: 'stdio' or 'streamable-http'",
    )

    mcp_host: str = Field(
        default="127.0.0.1",
        alias="MCP_HOST",
        description="Bind host for Streamable HTTP transport",
    )

    mcp_port: int = Field(
        default=8000,
        alias="MCP_PORT",
        ge=1,
        le=65535,
        description="Bind port for Streamable HTTP transport",
    )

    mcp_path: str = Field(
        default="/mcp",
        alias="MCP_PATH",
        description="Path prefix for Streamable HTTP transport",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level",
    )

    max_text_length: int = Field(
        default=4000,
        alias="MAX_TEXT_LENGTH",
        ge=100,
        le=50000,
        description="Maximum character length before truncating ticket content",
    )

    @field_validator("freshdesk_domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: str) -> str:
        """Strip protocol, .freshdesk.com suffix, slashes, and whitespace."""
        if not isinstance(v, str):
            raise ValueError("FRESHDESK_DOMAIN must be a non-empty string.")
        cleaned = v.strip().lower()
        # Remove scheme
        cleaned = re.sub(r"^https?://", "", cleaned)
        # Remove trailing paths or slashes
        cleaned = cleaned.split("/")[0]
        # Remove freshdesk.com suffix if present
        if cleaned.endswith(".freshdesk.com"):
            cleaned = cleaned[: -len(".freshdesk.com")]

        if not cleaned:
            raise ValueError("FRESHDESK_DOMAIN cannot be empty.")
        if not _DOMAIN_LABEL_REGEX.match(cleaned):
            raise ValueError(
                f"Invalid FRESHDESK_DOMAIN '{cleaned}'. Domain label must be alphanumeric "
                "with optional single hyphens."
            )
        return cleaned

    @field_validator("freshdesk_api_key", mode="after")
    @classmethod
    def validate_api_key(cls, v: SecretStr) -> SecretStr:
        """Ensure API key is not empty or an obvious placeholder."""
        raw = v.get_secret_value().strip()
        if not raw:
            raise ValueError("FRESHDESK_API_KEY cannot be empty.")
        if raw.lower() in _PLACEHOLDER_KEYS:
            raise ValueError(
                "FRESHDESK_API_KEY contains placeholder value. Please provide a valid Freshdesk API key."
            )
        return v

    @property
    def api_base_url(self) -> str:
        """Return the normalized Freshdesk REST API v2 base URL."""
        return f"https://{self.freshdesk_domain}.freshdesk.com/api/v2"


def load_settings() -> Settings:
    """Safely instantiate and validate application Settings.

    Raises:
        FreshdeskConfigurationError: If any configuration variable is missing or invalid.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise FreshdeskConfigurationError(
            message=f"Configuration validation failed: {exc}",
            details={"error_type": type(exc).__name__},
        ) from exc
