"""Decision Workspace API (PE-004A) — read-only aggregation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.services.decision_workspace import (
    DecisionWorkspaceNotFoundError,
    decision_workspace,
)

router = APIRouter(prefix="/api/decision-workspace", tags=["decision-workspace"])


@router.get("/{decision_id}")
def workspace(decision_id: UUID, session: Session = Depends(get_session)):
    try:
        return decision_workspace(session, decision_id)
    except DecisionWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
