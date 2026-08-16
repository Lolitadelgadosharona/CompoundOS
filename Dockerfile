# Production Dockerfile — CompoundOS V1
# Multi-stage build: lightweight final image, no dev deps.

FROM python:3.9-slim-bookworm AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

# Production defaults
ENV ENVIRONMENT=production
ENV HOST=0.0.0.0
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Migration-on-startup entrypoint (alembic upgrade head → uvicorn).
# Fails closed if the migration fails.
ENTRYPOINT ["/bin/sh", "scripts/entrypoint.sh"]
