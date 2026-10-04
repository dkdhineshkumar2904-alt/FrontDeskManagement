"""Unit tests for configuration loading and validation."""

import pytest
from pydantic import SecretStr, ValidationError

from freshdesk_mcp.config import Settings, load_settings
from freshdesk_mcp.exceptions import FreshdeskConfigurationError


def test_valid_configuration() -> None:
    """Verify valid settings initialize properly."""
    settings = Settings(
        FRESHDESK_DOMAIN="acme",
        FRESHDESK_API_KEY=SecretStr("valid_key_12345"),
        FRESHDESK_TIMEOUT=10.0,
        FRESHDESK_MAX_RETRIES=2,
        FRESHDESK_MAX_PAGES=4,
        MCP_TRANSPORT="stdio",
        LOG_LEVEL="INFO",
    )
    assert settings.freshdesk_domain == "acme"
    assert settings.freshdesk_api_key.get_secret_value() == "valid_key_12345"
    assert settings.api_base_url == "https://acme.freshdesk.com/api/v2"
    assert settings.freshdesk_timeout == 10.0
    assert settings.freshdesk_max_retries == 2
    assert settings.freshdesk_max_pages == 4
    assert settings.mcp_transport == "stdio"


@pytest.mark.parametrize(
    "raw_input,expected_subdomain",
    [
        ("mycompany", "mycompany"),
        ("MYCOMPANY", "mycompany"),
        ("mycompany.freshdesk.com", "mycompany"),
        ("https://mycompany.freshdesk.com", "mycompany"),
        ("http://mycompany.freshdesk.com/", "mycompany"),
        ("https://my-company-1.freshdesk.com/api/v2", "my-company-1"),
    ],
)
def test_domain_normalization(raw_input: str, expected_subdomain: str) -> None:
    """Verify various user input domain formats normalize to clean subdomain."""
    settings = Settings(
        FRESHDESK_DOMAIN=raw_input,
        FRESHDESK_API_KEY=SecretStr("valid_key_12345"),
    )
    assert settings.freshdesk_domain == expected_subdomain
    assert settings.api_base_url == f"https://{expected_subdomain}.freshdesk.com/api/v2"


@pytest.mark.parametrize(
    "invalid_domain",
    [
        "",
        "   ",
        "invalid domain with spaces",
        "invalid_with_underscores_in_dns",
        "!@#$%^",
    ],
)
def test_invalid_domain_rejection(invalid_domain: str) -> None:
    """Verify malformed domains raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(
            FRESHDESK_DOMAIN=invalid_domain,
            FRESHDESK_API_KEY=SecretStr("valid_key_12345"),
        )


@pytest.mark.parametrize(
    "placeholder",
    [
        "your_freshdesk_api_key_here",
        "your_api_key_here",
        "placeholder",
        "secret",
        "changeme",
        "",
    ],
)
def test_placeholder_api_key_rejection(placeholder: str) -> None:
    """Verify default placeholder API keys are rejected."""
    with pytest.raises(ValidationError):
        Settings(
            FRESHDESK_DOMAIN="acme",
            FRESHDESK_API_KEY=SecretStr(placeholder),
        )


def test_invalid_timeout_and_retries() -> None:
    """Verify out-of-bounds timeout and retry limits are rejected."""
    with pytest.raises(ValidationError):
        Settings(
            FRESHDESK_DOMAIN="acme",
            FRESHDESK_API_KEY=SecretStr("valid_key_12345"),
            FRESHDESK_TIMEOUT=-5.0,
        )

    with pytest.raises(ValidationError):
        Settings(
            FRESHDESK_DOMAIN="acme",
            FRESHDESK_API_KEY=SecretStr("valid_key_12345"),
            FRESHDESK_MAX_RETRIES=20,  # Max allowed is 10
        )


def test_load_settings_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load_settings raises FreshdeskConfigurationError when required env is missing."""
    monkeypatch.delenv("FRESHDESK_DOMAIN", raising=False)
    monkeypatch.delenv("FRESHDESK_API_KEY", raising=False)
    with pytest.raises(FreshdeskConfigurationError) as exc_info:
        load_settings()
    assert "Configuration validation failed" in exc_info.value.message
