from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.schemas import (
    AuditEventResponse,
    HouseholdCreate,
    HouseholdResponse,
    HouseholdUpdate,
)
from apps.api.services.households import (
    HouseholdAlreadyExistsError,
    HouseholdNotFoundError,
    NoHouseholdChangesError,
    create_household,
    read_current_audit_events,
    read_current_household,
    update_current_household,
)

router = APIRouter(prefix="/api/households", tags=["households"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create(payload: HouseholdCreate, session: DatabaseSession) -> HouseholdResponse:
    try:
        return HouseholdResponse.model_validate(create_household(session, payload))
    except HouseholdAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="A household profile already exists") from exc


@router.get("/current", response_model=HouseholdResponse)
def get_current(session: DatabaseSession) -> HouseholdResponse:
    try:
        return HouseholdResponse.model_validate(read_current_household(session))
    except HouseholdNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Household profile not found") from exc


@router.patch("/current", response_model=HouseholdResponse)
def update_current(payload: HouseholdUpdate, session: DatabaseSession) -> HouseholdResponse:
    try:
        return HouseholdResponse.model_validate(update_current_household(session, payload))
    except HouseholdNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Household profile not found") from exc
    except NoHouseholdChangesError as exc:
        raise HTTPException(status_code=400, detail="No household changes provided") from exc


@router.get("/current/audit-events", response_model=list[AuditEventResponse])
def get_current_audit_events(session: DatabaseSession) -> list[AuditEventResponse]:
    try:
        return [
            AuditEventResponse.model_validate(event)
            for event in read_current_audit_events(session)
        ]
    except HouseholdNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Household profile not found") from exc
