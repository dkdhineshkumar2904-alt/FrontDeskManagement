"""Unit tests for logging configuration and redaction filter."""

import logging

from freshdesk_mcp.logging_config import RedactingFilter, setup_logging


def test_redacting_filter_messages() -> None:
    """Verify sensitive tokens and Authorization headers are redacted from log records."""
    f = RedactingFilter()

    # Basic auth header redaction
    rec1 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting with Authorization: Basic dXNlcjpwYXNz",
        args=(),
        exc_info=None,
    )
    f.filter(rec1)
    assert "Authorization: Basic [REDACTED]" in rec1.msg
    assert "dXNlcjpwYXNz" not in rec1.msg

    # API key pattern redaction
    rec2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Using api_key='abcdef1234567890'",
        args=(),
        exc_info=None,
    )
    f.filter(rec2)
    assert "[REDACTED]" in rec2.msg
    assert "abcdef1234567890" not in rec2.msg

    # Bearer token redaction
    rec3 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Header Bearer eyJhbGciOiJIUzI1NiJ9.test",
        args=(),
        exc_info=None,
    )
    f.filter(rec3)
    assert "Bearer [REDACTED]" in rec3.msg


def test_redacting_filter_args() -> None:
    """Verify sensitive tokens in format string arguments are also redacted."""
    f = RedactingFilter()

    # Tuple args
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Request with %s and %s",
        args=("Authorization: Basic c2VjcmV0MTIz", "safe_val"),
        exc_info=None,
    )
    f.filter(rec)
    assert isinstance(rec.args, tuple)
    assert "Authorization: Basic [REDACTED]" in str(rec.args[0])
    assert str(rec.args[1]) == "safe_val"

    # Dict args
    rec_dict = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Dict payload %(auth)s",
        args={"auth": "Authorization: Basic c2VjcmV0", "other": 123},
        exc_info=None,
    )
    f.filter(rec_dict)
    assert isinstance(rec_dict.args, dict)
    assert "Authorization: Basic [REDACTED]" in str(rec_dict.args["auth"])


def test_setup_logging() -> None:
    """Verify setup_logging configures logger with appropriate level and redacting filter."""
    logger = setup_logging(log_level="DEBUG", transport="stdio")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) >= 1
    has_redacting = any(isinstance(f, RedactingFilter) for f in logger.handlers[0].filters)
    assert has_redacting is True
