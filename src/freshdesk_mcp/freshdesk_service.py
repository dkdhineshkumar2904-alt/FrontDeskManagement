"""Business logic and service orchestration layer for Freshdesk operations.

Coordinates between HTTP client, data normalization, pagination validation,
and defensive security handling.
"""

import logging
from datetime import datetime
from typing import Any

from freshdesk_mcp.config import Settings
from freshdesk_mcp.exceptions import FreshdeskValidationError
from freshdesk_mcp.freshdesk_client import FreshdeskClient
from freshdesk_mcp.pagination import build_pagination_meta, validate_pagination_params
from freshdesk_mcp.schemas import (
    ConnectorHealthResponse,
    ConversationSchema,
    GetConversationsResponse,
    GetTicketResponse,
    ListTicketsResponse,
    SearchTicketsResponse,
    TicketSchema,
    get_priority_name,
    get_status_name,
)
from freshdesk_mcp.security import (
    DATA_SAFETY_NOTICE,
    sanitize_dict_fields,
    sanitize_text,
    validate_search_query,
)

logger = logging.getLogger("freshdesk_mcp.service")


class FreshdeskService:
    """Service layer executing read-only Freshdesk operations with validation and normalization."""

    def __init__(self, settings: Settings, client: FreshdeskClient | None = None) -> None:
        self.settings = settings
        self.client = client or FreshdeskClient(settings)
        self._owned_client = client is None

    async def aclose(self) -> None:
        """Close service resources."""
        if self._owned_client:
            await self.client.aclose()

    def _normalize_ticket(self, raw: dict[str, Any]) -> TicketSchema:
        """Normalize raw Freshdesk ticket dictionary into TicketSchema."""
        ticket_id = int(raw.get("id", 0))
        subject = (
            sanitize_text(str(raw.get("subject", "No Subject")), self.settings.max_text_length)
            or ""
        )
        desc = sanitize_text(
            raw.get("description_text") or raw.get("description"), self.settings.max_text_length
        )

        status = int(raw.get("status", 2))
        priority = int(raw.get("priority", 1))

        tags = [str(t) for t in raw.get("tags", []) if t]
        custom_fields = sanitize_dict_fields(
            raw.get("custom_fields", {}) or {}, self.settings.max_text_length
        )

        return TicketSchema(
            id=ticket_id,
            subject=subject,
            description_text=desc,
            status=status,
            status_name=get_status_name(status),
            priority=priority,
            priority_name=get_priority_name(priority),
            type=raw.get("type"),
            requester_id=raw.get("requester_id"),
            responder_id=raw.get("responder_id"),
            group_id=raw.get("group_id"),
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
            due_by=str(raw.get("due_by")) if raw.get("due_by") else None,
            tags=tags,
            custom_fields=custom_fields,
            conversations=None,
        )

    def _normalize_conversation(self, raw: dict[str, Any]) -> ConversationSchema:
        """Normalize raw Freshdesk conversation dictionary into ConversationSchema."""
        body = sanitize_text(raw.get("body_text") or raw.get("body"), self.settings.max_text_length)
        return ConversationSchema(
            id=int(raw.get("id", 0)),
            ticket_id=int(raw.get("ticket_id", 0)),
            body_text=body,
            user_id=raw.get("user_id"),
            incoming=bool(raw.get("incoming", False)),
            private=bool(raw.get("private", False)),
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
        )

    async def list_tickets(
        self,
        page: int = 1,
        per_page: int = 20,
        status: int | None = None,
        priority: int | None = None,
        requester_id: int | None = None,
        updated_since: str | None = None,
    ) -> ListTicketsResponse:
        """Retrieve paginated tickets with optional filters."""
        page, per_page = validate_pagination_params(page, per_page, max_per_page=100)

        # Validate updated_since format if provided
        if updated_since:
            try:
                datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
            except ValueError as exc:
                raise FreshdeskValidationError(
                    f"Invalid updated_since format '{updated_since}'. Must be an ISO 8601 timestamp (e.g. '2026-09-01T10:00:00Z').",
                    details={"updated_since": updated_since},
                ) from exc

        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "requester_id": requester_id,
            "updated_since": updated_since,
        }

        raw_data = await self.client.get("/tickets", params=params)

        if not isinstance(raw_data, list):
            raise FreshdeskValidationError(
                "Unexpected response format from Freshdesk /tickets endpoint."
            )

        normalized_tickets: list[TicketSchema] = []
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            ticket = self._normalize_ticket(item)
            # Apply client-side status and priority filtering if specified
            if status is not None and ticket.status != status:
                continue
            if priority is not None and ticket.priority != priority:
                continue
            normalized_tickets.append(ticket)

        pagination = build_pagination_meta(
            page=page,
            per_page=per_page,
            items_count=len(normalized_tickets),
            max_pages_allowed=self.settings.freshdesk_max_pages,
        )

        return ListTicketsResponse(
            success=True,
            tickets=normalized_tickets,
            pagination=pagination,
            data_safety_notice=DATA_SAFETY_NOTICE,
        )

    async def get_ticket(
        self,
        ticket_id: int,
        include_conversations: bool = False,
    ) -> GetTicketResponse:
        """Retrieve a single ticket by ID, optionally including conversation thread."""
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            raise FreshdeskValidationError(
                f"Invalid ticket_id '{ticket_id}'. Must be a positive integer.",
                details={"ticket_id": ticket_id},
            )

        raw_ticket = await self.client.get(f"/tickets/{ticket_id}")
        if not isinstance(raw_ticket, dict):
            raise FreshdeskValidationError(
                "Unexpected response format from Freshdesk get ticket endpoint."
            )

        ticket = self._normalize_ticket(raw_ticket)

        if include_conversations:
            conv_data = await self.client.get(
                f"/tickets/{ticket_id}/conversations", params={"per_page": 30}
            )
            if isinstance(conv_data, list):
                ticket.conversations = [
                    self._normalize_conversation(c) for c in conv_data if isinstance(c, dict)
                ]

        return GetTicketResponse(
            success=True,
            ticket=ticket,
            data_safety_notice=DATA_SAFETY_NOTICE,
        )

    async def search_tickets(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> SearchTicketsResponse:
        """Search tickets using Freshdesk Search API v2 query syntax."""
        cleaned_query = validate_search_query(query)

        # Freshdesk Search API caps per_page at 30
        effective_per_page = min(per_page, 30)
        page, _ = validate_pagination_params(page, effective_per_page, max_per_page=30)

        # Freshdesk search syntax requires wrapping the query in double quotes
        formatted_query = (
            cleaned_query
            if cleaned_query.startswith('"') and cleaned_query.endswith('"')
            else f'"{cleaned_query}"'
        )

        params = {
            "query": formatted_query,
            "page": page,
        }

        raw_data = await self.client.get("/search/tickets", params=params)

        results: list[dict[str, Any]] = []
        if isinstance(raw_data, dict) and "results" in raw_data:
            results = raw_data.get("results", [])
        elif isinstance(raw_data, list):
            results = raw_data

        tickets = [self._normalize_ticket(item) for item in results if isinstance(item, dict)]

        pagination = build_pagination_meta(
            page=page,
            per_page=effective_per_page,
            items_count=len(tickets),
            max_pages_allowed=self.settings.freshdesk_max_pages,
        )

        search_summary = (
            f"Retrieved {len(tickets)} tickets matching query '{cleaned_query}' on page {page}. "
            "Note: Freshdesk search results have up to 5-10 minutes indexing latency and a maximum cap of 300 results."
        )

        return SearchTicketsResponse(
            success=True,
            tickets=tickets,
            pagination=pagination,
            search_summary=search_summary,
            data_safety_notice=DATA_SAFETY_NOTICE,
        )

    async def get_ticket_conversations(
        self,
        ticket_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> GetConversationsResponse:
        """Retrieve conversation messages and notes for a ticket."""
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            raise FreshdeskValidationError(
                f"Invalid ticket_id '{ticket_id}'. Must be a positive integer.",
                details={"ticket_id": ticket_id},
            )

        page, per_page = validate_pagination_params(page, per_page, max_per_page=100)

        raw_data = await self.client.get(
            f"/tickets/{ticket_id}/conversations",
            params={"page": page, "per_page": per_page},
        )

        conversations: list[ConversationSchema] = []
        if isinstance(raw_data, list):
            conversations = [
                self._normalize_conversation(item) for item in raw_data if isinstance(item, dict)
            ]

        pagination = build_pagination_meta(
            page=page,
            per_page=per_page,
            items_count=len(conversations),
            max_pages_allowed=self.settings.freshdesk_max_pages,
        )

        return GetConversationsResponse(
            success=True,
            ticket_id=ticket_id,
            conversations=conversations,
            pagination=pagination,
            data_safety_notice=DATA_SAFETY_NOTICE,
        )

    async def get_health(self) -> ConnectorHealthResponse:
        """Perform connector self-check and Freshdesk API connectivity ping."""
        is_connected, latency_ms, _ = await self.client.verify_credentials()

        status = "healthy" if is_connected else "degraded"
        conn_status = "connected" if is_connected else "disconnected"

        return ConnectorHealthResponse(
            success=True,
            status=status,
            freshdesk_connectivity=conn_status,
            transport=self.settings.mcp_transport,
            api_latency_ms=latency_ms,
            version="0.1.0",
            read_only_enforced=True,
        )
