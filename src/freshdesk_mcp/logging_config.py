"""Structured and secure logging configuration for Freshdesk MCP Connector.

Ensures credentials, Authorization headers, and sensitive tokens are never logged.
Routes logs to stderr to preserve stdout exclusively for MCP stdio protocol traffic.
"""

import logging
import re
import sys

# Patterns matching sensitive keys and auth headers
_AUTH_HEADER_REGEX = re.compile(r"(Authorization:\s*Basic\s+)[A-Za-z0-9+/=]+", re.IGNORECASE)
_API_KEY_REGEX = re.compile(r"(api[_-]?key[\"':\s=]+)([A-Za-z0-9_\-]{8,})", re.IGNORECASE)
_BEARER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE)


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive patterns from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(v) if isinstance(v, str) else v for v in record.args
                )
        return True

    @classmethod
    def _redact(cls, text: str) -> str:
        s = _AUTH_HEADER_REGEX.sub(r"\1[REDACTED]", text)
        s = _API_KEY_REGEX.sub(r"\1[REDACTED]", s)
        s = _BEARER_REGEX.sub(r"\1[REDACTED]", s)
        return s


def setup_logging(log_level: str = "INFO", transport: str = "stdio") -> logging.Logger:
    """Configure connector logging with safety filter and stderr output.

    Args:
        log_level: Desired log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        transport: MCP transport mode. In stdio mode, logging MUST use stderr.
    """
    logger = logging.getLogger("freshdesk_mcp")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on multiple setup calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)

    # Prevent root logger propagation to prevent uncaught stdout leaks
    logger.propagate = False
    return logger
