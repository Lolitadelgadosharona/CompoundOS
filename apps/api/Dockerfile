FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG GIT_SHA
ARG BUILD_TIMESTAMP
ARG APP_VERSION=0.2.0
RUN test "${#GIT_SHA}" -eq 40 && test -n "$BUILD_TIMESTAMP"
ENV COMPOUNDOS_GIT_SHA=$GIT_SHA COMPOUNDOS_BUILD_TIMESTAMP=$BUILD_TIMESTAMP COMPOUNDOS_APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.revision=$GIT_SHA org.opencontainers.image.created=$BUILD_TIMESTAMP org.opencontainers.image.version=$APP_VERSION
WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY apps ./apps
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
