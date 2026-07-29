"""Sprint 007 Slice B — Mutation gate middleware.

Blocks all POST/PATCH/PUT/DELETE when DB unavailable or migration mismatch.
GET/HEAD/OPTIONS pass through for degraded read-only operation.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from apps.api.config import get_database_url

MUTATION_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
ALLOWED_PATHS = {"/api/health/live", "/api/health/ready", "/api/health/full"}
EXPECTED_HEAD = "0017_backup_daily_allowlist"


async def mutation_gate(request: Request, call_next):
    if request.method not in MUTATION_METHODS:
        return await call_next(request)

    if request.url.path in ALLOWED_PATHS:
        return await call_next(request)

    try:
        engine = create_engine(get_database_url())
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                row = conn.execute(text(
                    "SELECT version_num FROM alembic_version"
                )).fetchone()
                if not row or row[0] != EXPECTED_HEAD:
                    return JSONResponse(
                        status_code=503,
                        content={"detail": "System degraded — migration mismatch."},
                    )
        finally:
            engine.dispose()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"detail": "System unavailable — database not reachable."},
        )

    return await call_next(request)
