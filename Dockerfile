# Production Dockerfile — CompoundOS V1
# Multi-stage build: lightweight final image, no dev deps.

FROM python:3.11-slim-bookworm AS builder

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --user -r requirements.lock

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

ARG GIT_SHA
ARG BUILD_TIMESTAMP
ARG APP_VERSION=0.2.0
RUN test "${#GIT_SHA}" -eq 40 && test -n "$BUILD_TIMESTAMP"
ENV COMPOUNDOS_GIT_SHA=$GIT_SHA COMPOUNDOS_BUILD_TIMESTAMP=$BUILD_TIMESTAMP COMPOUNDOS_APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.revision=$GIT_SHA org.opencontainers.image.created=$BUILD_TIMESTAMP org.opencontainers.image.version=$APP_VERSION
COPY apps ./apps
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh

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
