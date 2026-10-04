"""Reusable pagination handling for Freshdesk MCP Connector.

Enforces bounds, prevents unbounded queries, caps maximum pages,
and produces standardized pagination metadata.
"""

from typing import TypeVar

from pydantic import BaseModel, Field

from freshdesk_mcp.exceptions import FreshdeskValidationError

T = TypeVar("T")


class PaginationRequest(BaseModel):
    """Validated pagination request parameters."""

    page: int = Field(default=1, ge=1, description="Page number, 1-indexed")
    per_page: int = Field(default=20, ge=1, le=100, description="Results per page (max 100)")


class PaginationMeta(BaseModel):
    """Standard pagination metadata returned to MCP clients and AI agents."""

    page: int = Field(description="Current page number")
    per_page: int = Field(description="Requested items per page")
    total_retrieved: int = Field(description="Number of items returned in current response")
    has_more: bool = Field(description="Indicates whether more results are likely available")
    max_pages_reached: bool = Field(
        default=False,
        description="True if pagination was capped by server configured FRESHDESK_MAX_PAGES",
    )


def validate_pagination_params(
    page: int,
    per_page: int,
    max_per_page: int = 100,
) -> tuple[int, int]:
    """Validate and sanitize page and per_page parameters.

    Raises:
        FreshdeskValidationError: If parameters are outside allowed bounds.
    """
    if page < 1:
        raise FreshdeskValidationError(
            f"Invalid page parameter '{page}'. Page must be an integer greater than or equal to 1.",
            details={"page": page},
        )
    if per_page < 1 or per_page > max_per_page:
        raise FreshdeskValidationError(
            f"Invalid per_page parameter '{per_page}'. Must be between 1 and {max_per_page}.",
            details={"per_page": per_page, "max_allowed": max_per_page},
        )
    return page, per_page


def build_pagination_meta(
    page: int,
    per_page: int,
    items_count: int,
    max_pages_allowed: int,
) -> PaginationMeta:
    """Build standard pagination metadata from results."""
    # If the returned items count equals per_page, there may be more items
    has_more = items_count == per_page
    max_pages_reached = page >= max_pages_allowed

    # If max pages reached, has_more is effectively false for safety
    if max_pages_reached:
        has_more = False

    return PaginationMeta(
        page=page,
        per_page=per_page,
        total_retrieved=items_count,
        has_more=has_more,
        max_pages_reached=max_pages_reached,
    )
