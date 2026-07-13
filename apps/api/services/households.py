from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import AuditEvent, HouseholdProfile
from apps.api.repositories.households import (
    add_audit_event,
    add_household,
    get_current_household,
    list_audit_events,
)
from apps.api.schemas import HouseholdCreate, HouseholdUpdate


class HouseholdAlreadyExistsError(Exception):
    pass


class HouseholdNotFoundError(Exception):
    pass


class NoHouseholdChangesError(Exception):
    pass


def _is_singleton_conflict(exc: IntegrityError) -> bool:
    diagnostics = getattr(exc.orig, "diag", None)
    return (
        getattr(diagnostics, "constraint_name", None)
        == "uq_household_profiles_singleton_key"
    )


def create_household(session: Session, payload: HouseholdCreate) -> HouseholdProfile:
    values = payload.model_dump()
    try:
        with session.begin():
            household = add_household(session, values)
            add_audit_event(
                session,
                household_id=household.id,
                action="household.created",
                changed_fields=list(values),
            )
        return household
    except IntegrityError as exc:
        session.rollback()
        if not _is_singleton_conflict(exc):
            raise
        raise HouseholdAlreadyExistsError from exc


def read_current_household(session: Session) -> HouseholdProfile:
    household = get_current_household(session)
    if household is None:
        raise HouseholdNotFoundError
    return household


def update_current_household(
    session: Session, payload: HouseholdUpdate
) -> HouseholdProfile:
    submitted = payload.model_dump(exclude_unset=True)
    if not submitted:
        raise NoHouseholdChangesError

    with session.begin():
        household = get_current_household(session)
        if household is None:
            raise HouseholdNotFoundError

        changed = [name for name, value in submitted.items() if getattr(household, name) != value]
        if not changed:
            raise NoHouseholdChangesError

        for name in changed:
            setattr(household, name, submitted[name])
        household.updated_at = datetime.now(timezone.utc)
        session.flush()
        add_audit_event(
            session,
            household_id=household.id,
            action="household.updated",
            changed_fields=changed,
        )
    return household


def read_current_audit_events(session: Session) -> list[AuditEvent]:
    household = read_current_household(session)
    return list_audit_events(session, household.id)
