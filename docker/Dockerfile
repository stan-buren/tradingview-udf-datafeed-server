# ─── TradingView UDF Server ───────────────────────
# Multi-stage Docker build for production deployment

FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies in a separate layer
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ ./src/
COPY frontend/ ./frontend/

# Install the project itself
RUN uv sync --frozen --no-dev

# ─── Runtime Stage ─────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/frontend /app/frontend

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health')"

CMD ["uvicorn", "src.udf_server.main:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "2"]
