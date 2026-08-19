"""Capital Allocation API (PE-003B.1) — read-only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.services import capital_allocation as service

router = APIRouter(prefix="/api/capital-allocation", tags=["capital-allocation"])


@router.get("")
def capital_allocation(session: Session = Depends(get_session)):
    return service.capital_allocation(session)
