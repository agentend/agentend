# Multi-stage build for agentend

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE ./

# Create venv and install dependencies
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools && \
    /opt/venv/bin/pip install -e .

# Stage 2: Runtime image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 agentend && \
    chown -R agentend:agentend /app

USER agentend

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run agentend server
CMD ["uvicorn", "agentend.main:app", "--host", "0.0.0.0", "--port", "8000"]
