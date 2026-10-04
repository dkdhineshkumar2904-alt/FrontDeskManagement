"""Pydantic schemas and data models for Freshdesk MCP Connector.

Defines standardized input and output structures for MCP tools,
ensuring strict validation and clean normalization.
"""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field

from freshdesk_mcp.pagination import PaginationMeta
from freshdesk_mcp.security import DATA_SAFETY_NOTICE


class TicketStatus(IntEnum):
    """Documented Freshdesk ticket status codes."""

    OPEN = 2
    PENDING = 3
    RESOLVED = 4
    CLOSED = 5


class TicketPriority(IntEnum):
    """Documented Freshdesk ticket priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


STATUS_NAMES: dict[int, str] = {
    TicketStatus.OPEN: "Open",
    TicketStatus.PENDING: "Pending",
    TicketStatus.RESOLVED: "Resolved",
    TicketStatus.CLOSED: "Closed",
}

PRIORITY_NAMES: dict[int, str] = {
    TicketPriority.LOW: "Low",
    TicketPriority.MEDIUM: "Medium",
    TicketPriority.HIGH: "High",
    TicketPriority.URGENT: "Urgent",
}


def get_status_name(status_code: int) -> str:
    """Return friendly name for status code, or 'Unknown'."""
    return STATUS_NAMES.get(status_code, f"Status_{status_code}")


def get_priority_name(priority_code: int) -> str:
    """Return friendly name for priority code, or 'Unknown'."""
    return PRIORITY_NAMES.get(priority_code, f"Priority_{priority_code}")


class ConversationSchema(BaseModel):
    """Normalized Freshdesk conversation (reply or note) item."""

    id: int = Field(description="Unique conversation entry ID")
    ticket_id: int = Field(description="Associated ticket ID")
    body_text: str | None = Field(default=None, description="Plain text content of reply or note")
    user_id: int | None = Field(default=None, description="ID of the user who posted the message")
    incoming: bool = Field(default=False, description="True if sent by customer, False if agent")
    private: bool = Field(default=False, description="True if internal note, False if public reply")
    created_at: str = Field(description="Timestamp in ISO 8601 format")
    updated_at: str = Field(description="Timestamp in ISO 8601 format")


class TicketSchema(BaseModel):
    """Normalized, safe Freshdesk ticket entity."""

    id: int = Field(description="Unique Freshdesk ticket ID")
    subject: str = Field(description="Subject title of the ticket")
    description_text: str | None = Field(default=None, description="Plain text ticket description")
    status: int = Field(description="Numeric status code (2=Open, 3=Pending, 4=Resolved, 5=Closed)")
    status_name: str = Field(description="Human-readable status label")
    priority: int = Field(description="Numeric priority code (1=Low, 2=Medium, 3=High, 4=Urgent)")
    priority_name: str = Field(description="Human-readable priority label")
    type: str | None = Field(
        default=None, description="Ticket type category (e.g. Incident, Question)"
    )
    requester_id: int | None = Field(default=None, description="Contact ID of the requester")
    responder_id: int | None = Field(default=None, description="Agent ID assigned to this ticket")
    group_id: int | None = Field(default=None, description="Group ID assigned to this ticket")
    created_at: str = Field(description="Creation timestamp in ISO 8601 format")
    updated_at: str = Field(description="Last update timestamp in ISO 8601 format")
    due_by: str | None = Field(default=None, description="SLA due date timestamp")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom field values")
    conversations: list[ConversationSchema] | None = Field(
        default=None,
        description="Ticket conversation thread if explicitly requested",
    )


class ListTicketsResponse(BaseModel):
    """Response returned by list_tickets tool."""

    success: bool = True
    tickets: list[TicketSchema] = Field(description="List of tickets retrieved")
    pagination: PaginationMeta = Field(description="Pagination details")
    data_safety_notice: str = Field(
        default=DATA_SAFETY_NOTICE,
        description="Security advisory for handling untrusted user content",
    )


class GetTicketResponse(BaseModel):
    """Response returned by get_ticket tool."""

    success: bool = True
    ticket: TicketSchema = Field(description="Retrieved ticket data")
    data_safety_notice: str = Field(
        default=DATA_SAFETY_NOTICE,
        description="Security advisory for handling untrusted user content",
    )


class SearchTicketsResponse(BaseModel):
    """Response returned by search_tickets tool."""

    success: bool = True
    tickets: list[TicketSchema] = Field(description="List of matching tickets")
    pagination: PaginationMeta = Field(description="Pagination details")
    search_summary: str = Field(description="Summary of query execution and limitations")
    data_safety_notice: str = Field(
        default=DATA_SAFETY_NOTICE,
        description="Security advisory for handling untrusted user content",
    )


class GetConversationsResponse(BaseModel):
    """Response returned by get_ticket_conversations tool."""

    success: bool = True
    ticket_id: int = Field(description="ID of the ticket")
    conversations: list[ConversationSchema] = Field(description="List of conversation items")
    pagination: PaginationMeta = Field(description="Pagination details")
    data_safety_notice: str = Field(
        default=DATA_SAFETY_NOTICE,
        description="Security advisory for handling untrusted user content",
    )


class ConnectorHealthResponse(BaseModel):
    """Response returned by get_connector_health tool."""

    success: bool = True
    status: str = Field(description="'healthy', 'degraded', or 'unhealthy'")
    freshdesk_connectivity: str = Field(description="'connected', 'disconnected', or 'unverified'")
    transport: str = Field(description="Configured MCP transport ('stdio' or 'streamable-http')")
    api_latency_ms: float | None = Field(
        default=None,
        description="Freshdesk API round-trip ping latency in milliseconds",
    )
    version: str = Field(description="Connector release version")
    read_only_enforced: bool = Field(
        default=True,
        description="Indicates whether strict read-only safety guard is active",
    )


class ErrorResponse(BaseModel):
    """Standardized error structure returned to MCP clients."""

    success: bool = False
    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error explanation")
    retryable: bool = Field(description="Whether retrying the operation is appropriate")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Safe supplementary context (never contains secrets)",
    )
