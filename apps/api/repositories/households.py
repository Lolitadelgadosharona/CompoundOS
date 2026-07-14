from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import AuditEvent, HouseholdProfile

AUDIT_ACTOR = "local-owner"
HOUSEHOLD_ENTITY_TYPE = "HouseholdProfile"


def get_current_household(session: Session) -> HouseholdProfile | None:
    return session.scalar(select(HouseholdProfile))


def add_household(session: Session, values: dict[str, Any]) -> HouseholdProfile:
    household = HouseholdProfile(**values)
    session.add(household)
    session.flush()
    return household


def add_audit_event(
    session: Session,
    *,
    household_id: UUID,
    action: str,
    changed_fields: list[str],
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        actor=AUDIT_ACTOR,
        action=action,
        entity_type=HOUSEHOLD_ENTITY_TYPE,
        entity_id=household_id,
        event_metadata={"changed_fields": sorted(changed_fields)},
    )
    session.add(event)
    session.flush()
    return event


def list_audit_events(session: Session, household_id: UUID) -> list[AuditEvent]:
    statement = (
        select(AuditEvent)
        .where(AuditEvent.household_id == household_id)
        .order_by(AuditEvent.sequence_number.asc())
    )
    return list(session.scalars(statement))
