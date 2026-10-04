# Operational Boundaries & Known Limitations

This document outlines architectural and API-level boundaries to ensure predictable production deployment.

---

## 1. Freshdesk REST API v2 Boundaries

### 1.1 Search API Limitations
- **Indexing Lag:** Freshdesk Search API v2 relies on backend search indexing. Tickets created or updated within the last 5–10 minutes may not immediately appear in `search_tickets` queries. For immediate inspection of known tickets, use `get_ticket` directly.
- **Maximum 300 Results Cap:** Freshdesk Search API enforces a hard ceiling of 300 results (10 pages $\times$ 30 tickets per page). Searches cannot retrieve records past page 10.
- **Page Size Restriction:** Unlike the standard tickets endpoint (which permits up to 100 tickets/page), the Freshdesk Search endpoint caps `per_page` at 30. Requests specifying larger values are safely clamped to 30.
- **Query Formatting Requirements:** Queries must use Freshdesk search syntax and double quotes (e.g. `"status:2 AND priority:3"`). Arbitrary free-text searches may fail or return empty sets if syntax is invalid.

### 1.2 Rate Limits & Plan Tiers
Freshdesk enforces rate limits based on account tier:
- **Sprout / Blossom:** 50 requests / minute
- **Garden:** 100 requests / minute
- **Estate:** 400 requests / minute
- **Forest:** 700 requests / minute

The connector respects the `Retry-After` header when HTTP 429 occurs, with exponential backoff and jitter. If an account sustains heavy traffic from other integrations, tool calls may experience delayed responses while backing off.

### 1.3 Pagination Safety Cap
To prevent unbounded memory growth and token bloat in LLM contexts, the connector imposes `FRESHDESK_MAX_PAGES` (default: 5 pages). Calls will not fetch beyond this depth in a single execution.

---

## 2. Testing vs Live Integration

- **Automated Tests:** Unit and integration tests run against declarative mocks powered by `respx`. They require zero API keys and no internet connection.
- **Live Freshdesk Verification:** To verify against a live Freshdesk account:
  1. Ensure the Freshdesk user has at least the **Agent** role with view permissions on relevant ticket groups.
  2. Set `FRESHDESK_DOMAIN` and `FRESHDESK_API_KEY` in `.env`.
  3. Invoke `get_connector_health` to verify connectivity and latency.
