"""Setup readiness API — read-only (M7-001).

Exposes bootstrap readiness only. No secrets, no keys, no credential
values, no writes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.services.readiness_service import readiness_status

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    return readiness_status(session)
