# ==============================================================================
# Freshdesk MCP Connector - Production Container Image
# ==============================================================================
FROM python:3.12-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install security updates and build requirements
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create a non-privileged user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

# Copy dependency specifications first for layer caching
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && \
    pip install hatchling && \
    pip install .

# Copy application source code
COPY src/ ./src/

# Set ownership to unprivileged user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose Streamable HTTP port
EXPOSE 8000

# Default environment configuration
ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# Health check probe for Streamable HTTP mode
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/mcp || exit 1

# Launch MCP server
ENTRYPOINT ["freshdesk-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
