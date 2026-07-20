"""Sprint 007 Slice B — Health API router.

Read-only. No mutation, repair, restart, or restore endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.health_schemas import (
    ComponentHealthResponse,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)
from apps.api.services.health_service import EXPECTED_MIGRATION_HEAD, run_all_checks, _safe

router = APIRouter(prefix="/api/health", tags=["health"])


# ═══════════════════════════════════════════════════════════════════════════
# Liveness — minimal, no external calls
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse(checked_at=datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════
# Readiness — checks DB + schema compatibility
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/ready", response_model=ReadinessResponse)
def readiness(session: Session = Depends(get_session)) -> ReadinessResponse:
    now = datetime.now(timezone.utc)
    try:
        session.execute(text("SELECT 1")).fetchone()
    except Exception as e:
        return ReadinessResponse(ready=False, reason=_safe(str(e)), checked_at=now)

    try:
        row = session.execute(text(
            "SELECT version_num FROM alembic_version"
        )).fetchone()
        if not row or row[0] != EXPECTED_MIGRATION_HEAD:
            return ReadinessResponse(
                ready=False,
                reason=f"Migration head mismatch: expected {EXPECTED_MIGRATION_HEAD}",
                checked_at=now,
            )
    except Exception as e:
        return ReadinessResponse(ready=False, reason=_safe(str(e)), checked_at=now)

    return ReadinessResponse(ready=True, reason="Ready", checked_at=now)


# ═══════════════════════════════════════════════════════════════════════════
# Full health
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/full", response_model=HealthResponse)
def full_health(session: Session = Depends(get_session)) -> HealthResponse:
    result = run_all_checks(session)
    return HealthResponse(
        overall=result.overall,
        components=[
            ComponentHealthResponse(
                component=c.component, status=c.status,
                reason=c.reason, last_checked=c.last_checked,
                details=c.details,
            )
            for c in result.components
        ],
        checked_at=result.checked_at,
    )

