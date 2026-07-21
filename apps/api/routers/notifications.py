"""Sprint 007 Slice C — Notification API router V2 (integrity hardened)."""

from __future__ import annotations

from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.notification_schemas import (
    NotificationEventResponse,
    PreferencesResponse,
    PreferencesUpdate,
)
from apps.api.services.notification_service import (
    acknowledge,
    get_preferences,
    list_events,
    update_preferences,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/events", response_model=list[NotificationEventResponse])
def get_events(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[NotificationEventResponse]:
    events = list_events(session, limit=limit, offset=offset)
    return [NotificationEventResponse.model_validate(e) for e in events]


@router.post("/events/{event_id}/acknowledge", status_code=204)
def ack_event(
    event_id: UUID,
    session: Session = Depends(get_session),
) -> Response:
    acknowledge(session, event_id)
    return Response(status_code=204)


@router.get("/preferences", response_model=PreferencesResponse)
def get_prefs(
    session: Session = Depends(get_session),
) -> PreferencesResponse:
    prefs = get_preferences(session)
    return PreferencesResponse(
        id=prefs.id,
        quiet_hours_start=str(prefs.quiet_hours_start),
        quiet_hours_end=str(prefs.quiet_hours_end),
        timezone=prefs.timezone,
        enabled=prefs.enabled,
        enabled_sources=prefs.enabled_sources or [],
        enabled_severities=prefs.enabled_severities or [],
        updated_at=prefs.updated_at,
    )


@router.patch("/preferences", response_model=PreferencesResponse)
def patch_prefs(
    payload: PreferencesUpdate,
    session: Session = Depends(get_session),
) -> PreferencesResponse:
    start = time.fromisoformat(payload.quiet_hours_start) if payload.quiet_hours_start else None
    end = time.fromisoformat(payload.quiet_hours_end) if payload.quiet_hours_end else None
    prefs = update_preferences(
        session,
        quiet_hours_start=start,
        quiet_hours_end=end,
        tz=payload.timezone,
        enabled=payload.enabled,
        enabled_sources=payload.enabled_sources,
        enabled_severities=payload.enabled_severities,
    )
    return PreferencesResponse(
        id=prefs.id,
        quiet_hours_start=str(prefs.quiet_hours_start),
        quiet_hours_end=str(prefs.quiet_hours_end),
        timezone=prefs.timezone,
        enabled=prefs.enabled,
        enabled_sources=prefs.enabled_sources or [],
        enabled_severities=prefs.enabled_severities or [],
        updated_at=prefs.updated_at,
    )
