# =============================================================================
# ModelLab Production Multi-Stage Container Definition
# Targets:
#   1. ml-mcp-api: FastMCP 4 Server (Streamable HTTP / STDIO)
#   2. ml-worker-tabular-cpu: Sandboxed Asynchronous ML Execution Worker
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build & Dependency Resolution (Powered by Astral uv)
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS builder

# Grab uv binary from official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN uv venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Step 1: Install dependencies first (heavily cached by Docker)
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r pyproject.toml

# Step 2: Copy source code and install application without reinstalling dependencies
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

# -----------------------------------------------------------------------------
# Stage 2: ml-mcp-api (FastMCP 4 Control Plane Server)
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS ml-mcp-api

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source and configuration
COPY src/ /app/src/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

# Create unprivileged system user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /usr/sbin/nologin -d /app appuser && \
    mkdir -p /tmp/modellab && \
    chown -R appuser:appgroup /app /tmp/modellab

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["-m", "ml_mcp.server.http"]

# -----------------------------------------------------------------------------
# Stage 3: ml-worker-tabular-cpu (ML Training Execution Worker)
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS ml-worker-tabular-cpu

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY src/ /app/src/

# Create unprivileged system user
RUN groupadd -g 10002 workergroup && \
    useradd -u 10002 -g workergroup -s /usr/sbin/nologin -d /app workeruser && \
    mkdir -p /tmp/modellab_worker && \
    chown -R workeruser:workergroup /app /tmp/modellab_worker

USER 10002:10002

ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["-m", "ml_mcp.workers.daemon"]
