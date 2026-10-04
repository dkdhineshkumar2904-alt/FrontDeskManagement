"""Unit tests for pagination boundaries and metadata generation."""

import pytest

from freshdesk_mcp.exceptions import FreshdeskValidationError
from freshdesk_mcp.pagination import build_pagination_meta, validate_pagination_params


def test_validate_pagination_params_valid() -> None:
    """Verify normal pagination parameters pass validation."""
    page, per_page = validate_pagination_params(1, 20, max_per_page=100)
    assert page == 1
    assert per_page == 20

    page, per_page = validate_pagination_params(5, 100, max_per_page=100)
    assert page == 5
    assert per_page == 100


def test_validate_pagination_params_invalid_page() -> None:
    """Verify invalid page numbers raise FreshdeskValidationError."""
    with pytest.raises(FreshdeskValidationError) as exc:
        validate_pagination_params(0, 20)
    assert "Invalid page parameter" in exc.value.message

    with pytest.raises(FreshdeskValidationError):
        validate_pagination_params(-2, 20)


def test_validate_pagination_params_invalid_per_page() -> None:
    """Verify invalid per_page parameters raise FreshdeskValidationError."""
    with pytest.raises(FreshdeskValidationError) as exc:
        validate_pagination_params(1, 0)
    assert "Invalid per_page parameter" in exc.value.message

    with pytest.raises(FreshdeskValidationError):
        validate_pagination_params(1, 101, max_per_page=100)

    # For search API max_per_page is 30
    with pytest.raises(FreshdeskValidationError):
        validate_pagination_params(1, 35, max_per_page=30)


def test_build_pagination_meta() -> None:
    """Verify metadata generation accurately reflects items count and page limits."""
    # Full page returned, more items likely exist
    meta = build_pagination_meta(page=1, per_page=20, items_count=20, max_pages_allowed=5)
    assert meta.page == 1
    assert meta.per_page == 20
    assert meta.total_retrieved == 20
    assert meta.has_more is True
    assert meta.max_pages_reached is False

    # Partial page returned, end of list
    meta2 = build_pagination_meta(page=2, per_page=20, items_count=8, max_pages_allowed=5)
    assert meta2.total_retrieved == 8
    assert meta2.has_more is False
    assert meta2.max_pages_reached is False

    # Max pages ceiling reached
    meta3 = build_pagination_meta(page=5, per_page=20, items_count=20, max_pages_allowed=5)
    assert meta3.max_pages_reached is True
    assert meta3.has_more is False  # Forced to False due to ceiling
