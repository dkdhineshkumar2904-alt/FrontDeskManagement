"""Custom exception hierarchy for Freshdesk MCP Connector.

Provides structured, safe error representations preventing sensitive data
or raw stack traces from leaking to MCP clients and AI agents.
"""

from typing import Any


class FreshdeskBaseError(Exception):
    """Base exception for all Freshdesk MCP Connector errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        self.details = details or {}

    def to_tool_error_dict(self) -> dict[str, Any]:
        """Convert exception to safe, structured dictionary for MCP responses."""
        payload: dict[str, Any] = {
            "success": False,
            "error_code": self.error_code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class FreshdeskConfigurationError(FreshdeskBaseError):
    """Raised when environment variables or connector settings are invalid or missing."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            retryable=False,
            details=details,
        )


class FreshdeskAuthenticationError(FreshdeskBaseError):
    """Raised on HTTP 401 Unauthorized errors (invalid or expired API key)."""

    def __init__(
        self,
        message: str = "Freshdesk authentication failed. Please verify FRESHDESK_API_KEY and domain.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            retryable=False,
            details=details,
        )


class FreshdeskPermissionError(FreshdeskBaseError):
    """Raised on HTTP 403 Forbidden errors or when unauthorized mutation is attempted."""

    def __init__(
        self,
        message: str = "Freshdesk access denied. Insufficient permissions for requested resource.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            retryable=False,
            details=details,
        )


class FreshdeskNotFoundError(FreshdeskBaseError):
    """Raised on HTTP 404 Not Found errors."""

    def __init__(
        self,
        message: str = "Requested Freshdesk resource not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            retryable=False,
            details=details,
        )


class FreshdeskRateLimitError(FreshdeskBaseError):
    """Raised on HTTP 429 Rate Limit Exceeded errors."""

    def __init__(
        self,
        message: str = "Freshdesk API rate limit exceeded.",
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = details or {}
        if retry_after is not None:
            err_details["retry_after_seconds"] = retry_after
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            retryable=True,
            details=err_details,
        )
        self.retry_after = retry_after


class FreshdeskValidationError(FreshdeskBaseError):
    """Raised on invalid request arguments, query formatting, or HTTP 400/422 responses."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            retryable=False,
            details=details,
        )


class FreshdeskTimeoutError(FreshdeskBaseError):
    """Raised when an external request to Freshdesk times out."""

    def __init__(
        self,
        message: str = "Freshdesk API request timed out.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="REQUEST_TIMEOUT",
            retryable=True,
            details=details,
        )


class FreshdeskAPIError(FreshdeskBaseError):
    """Raised on general unexpected HTTP errors or server-side (5xx) failures."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = details or {}
        if status_code is not None:
            err_details["status_code"] = status_code
        # 5xx server errors are transient and retryable; 4xx are client errors
        is_retryable = (
            retryable if retryable is not None else (status_code is not None and status_code >= 500)
        )
        super().__init__(
            message=message,
            error_code="API_ERROR",
            retryable=is_retryable,
            details=err_details,
        )
        self.status_code = status_code
