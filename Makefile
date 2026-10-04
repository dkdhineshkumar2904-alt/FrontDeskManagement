.PHONY: help install test test-cov lint format typecheck check run-stdio run-http demo docker-build docker-up docker-down

help:
	@echo "Freshdesk MCP Connector - Development Targets:"
	@echo "  make install      Install package and dev dependencies"
	@echo "  make test         Run automated tests with pytest"
	@echo "  make test-cov     Run tests with coverage report"
	@echo "  make lint         Run ruff checks"
	@echo "  make format       Run ruff formatter"
	@echo "  make typecheck    Run strict type checking with mypy"
	@echo "  make check        Run lint, format check, and mypy"
	@echo "  make run-stdio    Run MCP server in stdio mode"
	@echo "  make run-http     Run MCP server in Streamable HTTP mode"
	@echo "  make demo         Run agent demonstration script"
	@echo "  make docker-build Build Docker container image"
	@echo "  make docker-up    Start service with Docker Compose"
	@echo "  make docker-down  Stop service with Docker Compose"

install:
	pip install --upgrade pip hatchling
	pip install -e ".[dev]"

test:
	pytest tests/

test-cov:
	pytest --cov=freshdesk_mcp --cov-report=term-missing tests/

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src tests

check: lint typecheck
	ruff format --check .

run-stdio:
	python -m freshdesk_mcp.server --transport stdio

run-http:
	python -m freshdesk_mcp.server --transport streamable-http --host 127.0.0.1 --port 8000

demo:
	python examples/mcp_client_demo.py

docker-build:
	docker build -t freshdesk-mcp-connector .

docker-up:
	docker compose up -d

docker-down:
	docker compose down
