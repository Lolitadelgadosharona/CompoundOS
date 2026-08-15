"""Observability API — read-only AI execution + cost endpoints (M6-001).

No mutation. Preserves the global auth boundary (GET routes pass through
the auth middleware unchanged).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.services import observability_service

router = APIRouter(prefix="/api/observability", tags=["observability"])


@router.get("/executions")
def executions(session: Session = Depends(get_session), limit: int = 50):
    """Recent LLM executions (newest first)."""
    return {"executions": observability_service.list_executions(session, limit)}


@router.get("/cost")
def cost(session: Session = Depends(get_session)):
    """Estimated cost breakdown (total + per-perspective + per-run)."""
    return observability_service.cost_breakdown(session)


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    """Aggregate AI execution summary (calls, tokens, cost, duration)."""
    return observability_service.execution_summary(session)
