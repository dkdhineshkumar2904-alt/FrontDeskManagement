"""Shared test fixtures and mock data for Freshdesk MCP Connector test suite."""

from typing import Any

import pytest
from pydantic import SecretStr

from freshdesk_mcp.config import Settings
from freshdesk_mcp.freshdesk_client import FreshdeskClient
from freshdesk_mcp.freshdesk_service import FreshdeskService


@pytest.fixture
def mock_settings() -> Settings:
    """Provide valid test settings without requiring real environment variables."""
    return Settings(
        FRESHDESK_DOMAIN="testcorp",
        FRESHDESK_API_KEY=SecretStr("test_secret_api_key_valid"),
        FRESHDESK_TIMEOUT=5.0,
        FRESHDESK_MAX_RETRIES=2,
        FRESHDESK_MAX_PAGES=3,
        FRESHDESK_CONCURRENCY_LIMIT=5,
        MCP_TRANSPORT="stdio",
        LOG_LEVEL="DEBUG",
        MAX_TEXT_LENGTH=500,
    )


@pytest.fixture
def raw_ticket_data() -> dict[str, Any]:
    """Provide realistic sample Freshdesk ticket payload."""
    return {
        "id": 101,
        "subject": "Payment webhook failure on Order #9872",
        "description_text": "Customer reported payment captured but merchant webhook not triggered.",
        "description": "<div>Customer reported payment captured but merchant webhook not triggered.</div>",
        "status": 2,  # Open
        "priority": 3,  # High
        "type": "Incident",
        "requester_id": 5001,
        "responder_id": 9001,
        "group_id": 10,
        "created_at": "2026-09-15T08:30:00Z",
        "updated_at": "2026-09-15T09:15:00Z",
        "due_by": "2026-09-16T08:30:00Z",
        "tags": ["payment_failure", "webhook", "high_priority"],
        "custom_fields": {
            "cf_merchant_id": "merch_abc123",
            "cf_transaction_id": "txn_xyz789",
        },
    }


@pytest.fixture
def raw_tickets_list(raw_ticket_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Provide a list of sample tickets."""
    ticket2 = dict(raw_ticket_data)
    ticket2["id"] = 102
    ticket2["subject"] = "Refund request pending for transaction #4412"
    ticket2["status"] = 3  # Pending
    ticket2["priority"] = 2  # Medium
    ticket2["tags"] = ["refund", "merchant_support"]

    ticket3 = dict(raw_ticket_data)
    ticket3["id"] = 103
    ticket3["subject"] = "Settlement delay query"
    ticket3["status"] = 4  # Resolved
    ticket3["priority"] = 1  # Low
    ticket3["tags"] = ["settlement"]

    return [raw_ticket_data, ticket2, ticket3]


@pytest.fixture
def raw_conversations_list() -> list[dict[str, Any]]:
    """Provide realistic conversation replies and notes."""
    return [
        {
            "id": 1001,
            "ticket_id": 101,
            "body_text": "Hello, our webhook listener for order 9872 failed to receive the payment.captured event.",
            "user_id": 5001,
            "incoming": True,
            "private": False,
            "created_at": "2026-09-15T08:30:00Z",
            "updated_at": "2026-09-15T08:30:00Z",
        },
        {
            "id": 1002,
            "ticket_id": 101,
            "body_text": "Investigating logs: gateway processed payment successfully; checking dispatcher queue.",
            "user_id": 9001,
            "incoming": False,
            "private": True,
            "created_at": "2026-09-15T08:45:00Z",
            "updated_at": "2026-09-15T08:45:00Z",
        },
        {
            "id": 1003,
            "ticket_id": 101,
            "body_text": "We identified a momentary network timeout on the dispatcher. The webhook has been redelivered.",
            "user_id": 9001,
            "incoming": False,
            "private": False,
            "created_at": "2026-09-15T09:15:00Z",
            "updated_at": "2026-09-15T09:15:00Z",
        },
    ]


@pytest.fixture
def freshdesk_client(mock_settings: Settings) -> FreshdeskClient:
    """Create a client with test settings."""
    return FreshdeskClient(mock_settings)


@pytest.fixture
def freshdesk_service(
    mock_settings: Settings, freshdesk_client: FreshdeskClient
) -> FreshdeskService:
    """Create a service with test settings and client."""
    return FreshdeskService(mock_settings, client=freshdesk_client)
