"""Sprint 007 Slice B — Mutation gate middleware.

Blocks all POST/PATCH/PUT/DELETE when DB unavailable or migration mismatch.
GET/HEAD/OPTIONS pass through for degraded read-only operation.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.api.database import SessionLocal


MUTATION_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
ALLOWED_PATHS = {"/api/health/live", "/api/health/ready", "/api/health/full"}


async def mutation_gate(request: Request, call_next):
    if request.method not in MUTATION_METHODS:
        return await call_next(request)

    if request.url.path in ALLOWED_PATHS:
        return await call_next(request)

    try:
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1")).fetchone()
            row = session.execute(text(
                "SELECT version_num FROM alembic_version"
            )).fetchone()
            expected = "0014_health_integrity"
            if not row or row[0] != expected:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "System degraded — migration mismatch. Try again later."},
                )
        finally:
            session.close()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"detail": "System unavailable — database not reachable. Try again later."},
        )

    return await call_next(request)
