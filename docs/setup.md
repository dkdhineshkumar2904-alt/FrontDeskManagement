# Setup & Development Guide

Comprehensive guide to installing, configuring, running, and verifying the **Freshdesk MCP Connector**.

---

## 1. System Requirements

* **Operating System:** Linux, macOS, or Windows
* **Python Version:** 3.12 or 3.13
* **Package Manager:** pip, uv, or poetry
* **Git:** Version 2.20+

---

## 2. Local Environment Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/razorpay/freshdesk-mcp-connector.git
cd freshdesk-mcp-connector
```

### Step 2: Create and Activate Virtual Environment
```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```bash
pip install -e ".[dev]"
```

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your Freshdesk credentials:
```ini
FRESHDESK_DOMAIN=your-subdomain
FRESHDESK_API_KEY=your_freshdesk_api_key_here
FRESHDESK_TIMEOUT=15.0
FRESHDESK_MAX_RETRIES=3
FRESHDESK_MAX_PAGES=5
FRESHDESK_CONCURRENCY_LIMIT=5
MCP_TRANSPORT=stdio
LOG_LEVEL=INFO
MAX_TEXT_LENGTH=4000
```

---

## 3. Running the Server

### Stdio Transport (Default)
Used by local MCP clients (Claude Desktop, Cursor, local agent CLI):
```bash
freshdesk-mcp --transport stdio
```

### Streamable HTTP Transport
Used for remote microservice deployments:
```bash
freshdesk-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```
Server is accessible at: `http://127.0.0.1:8000/mcp`

---

## 4. Verification & Testing

### Run Automated Tests
```bash
pytest --cov=freshdesk_mcp --cov-report=term-missing
```

### Run Static Analysis
```bash
ruff check .
ruff format --check .
mypy src tests
```

### Run Turnkey Demonstration
```bash
python examples/mcp_client_demo.py
```
