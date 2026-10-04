# Evaluator Demonstration Script

Follow this script to demonstrate the connector to hiring managers and reviewers.

---

## 1. Quick Verification (30 Seconds)

Run tests and linting to prove code quality, typing, and test coverage:

```bash
# 1. Run full test suite with coverage (Expect: 79 passed, 92%+ coverage)
pytest --cov=freshdesk_mcp --cov-report=term-missing

# 2. Run Ruff format and lint check (Expect: All checks passed)
ruff check .
ruff format --check .

# 3. Run Mypy strict type checking (Expect: Success: no issues found)
mypy src tests
```

---

## 2. Live Agent Demonstration Workflow (2 Minutes)

Execute the end-to-end runnable demonstration:

```bash
python examples/mcp_client_demo.py
```

### What the Demo Shows:
1. **Tool Discovery:** All 5 read-only tools discoverable with schemas.
2. **Health Check:** Evaluates process status and ping latency.
3. **List Open Tickets:** Fetches tickets filtered by `status=2`.
4. **Search Tickets:** Uses Freshdesk Search syntax for `tag:'payment_failure' AND priority:3`.
5. **Get Ticket & Conversations:** Drills into ticket `#90125` to inspect merchant inquiry and agent note.
6. **Defensive Error Handling:** Queries ticket `#99999` and gracefully returns `RESOURCE_NOT_FOUND` without crashing or leaking secrets.
7. **Agent Synthesis:** Demonstrates how an AI agent uses the structured data to formulate an incident diagnosis.

---

## 3. Architecture & Code Highlights

During the review, highlight:
- **`src/freshdesk_mcp/retry.py`:** Exponential backoff with full jitter, `Retry-After` header parsing, and concurrency limiting.
- **`src/freshdesk_mcp/security.py`:** Control character stripping, length truncation, and read-only HTTP method guard.
- **`src/freshdesk_mcp/logging_config.py`:** Real-time regex redaction of Basic auth and API keys from logs.
- **`src/freshdesk_mcp/server.py`:** Dual transport architecture supporting both `stdio` and `streamable-http`.
