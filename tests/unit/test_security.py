"""Unit tests for security, redaction, sanitization, and read-only assertions."""

import pytest

from freshdesk_mcp.exceptions import FreshdeskPermissionError
from freshdesk_mcp.security import (
    assert_read_only_method,
    mask_credential,
    sanitize_dict_fields,
    sanitize_text,
    validate_search_query,
)


def test_mask_credential() -> None:
    """Verify masking shields credentials with only small visible boundary."""
    assert mask_credential("secret_api_key_123456789") == "se...89"
    assert mask_credential("short") == "sh...rt"
    assert mask_credential("abc") == "***"
    assert mask_credential("") == ""


def test_sanitize_text_control_characters() -> None:
    """Verify non-printable control characters and null bytes are stripped."""
    dirty = "Hello\x00 World\x08 with \x1b special \x0c chars"
    clean = sanitize_text(dirty)
    assert clean == "Hello World with  special  chars"
    assert "\x00" not in (clean or "")
    assert "\x1b" not in (clean or "")


def test_sanitize_text_truncation() -> None:
    """Verify text exceeding maximum limit is truncated with warning appended."""
    long_text = "A" * 1000
    sanitized = sanitize_text(long_text, max_length=200)
    assert sanitized is not None
    assert len(sanitized.split("\n\n")[0]) == 200
    assert "[... TRUNCATED: Content exceeded 200 characters ...]" in sanitized


def test_sanitize_text_none_input() -> None:
    """Verify None input returns None safely."""
    assert sanitize_text(None) is None


def test_sanitize_dict_fields() -> None:
    """Verify recursive dictionary and list sanitization."""
    payload = {
        "title": "Clean Title",
        "description": "B" * 500,
        "nested": {
            "comment": "C" * 300,
            "int_val": 42,
        },
        "list_items": ["Normal", "D" * 400],
    }
    sanitized = sanitize_dict_fields(payload, max_length=100)
    assert sanitized["title"] == "Clean Title"
    assert "[... TRUNCATED" in sanitized["description"]
    assert "[... TRUNCATED" in sanitized["nested"]["comment"]
    assert sanitized["nested"]["int_val"] == 42
    assert sanitized["list_items"][0] == "Normal"
    assert "[... TRUNCATED" in sanitized["list_items"][1]


def test_assert_read_only_method() -> None:
    """Verify only GET is permitted; mutating methods raise FreshdeskPermissionError."""
    # Permitted
    assert_read_only_method("GET")
    assert_read_only_method("get")
    assert_read_only_method("  GET  ")

    # Prohibited
    for method in ["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
        with pytest.raises(FreshdeskPermissionError) as exc_info:
            assert_read_only_method(method)
        assert "is prohibited" in exc_info.value.message
        assert exc_info.value.error_code == "PERMISSION_DENIED"


def test_validate_search_query() -> None:
    """Verify search queries are checked for presence and length limits."""
    # Valid
    assert validate_search_query("status:2 AND priority:3") == "status:2 AND priority:3"

    # Empty
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_search_query("")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_search_query("   ")

    # Exceeding length
    with pytest.raises(ValueError, match="exceeds maximum allowed length"):
        validate_search_query("A" * 501, max_length=500)
