"""Service-level transaction boundaries for Decision Journal (Slice 3B)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.decision_schemas import (
    CONFIRM_REQUIRED_FIELDS,
    AppendCorrectionRequest,
    ArchiveDecisionRequest,
    ConfirmDecisionRequest,
    CreateDecisionRequest,
    DiscardDecisionRequest,
    UpdateDecisionDraftRequest,
)
from apps.api.models import (
    AuditEvent,
    Decision,
    DecisionConfirmedSnapshot,
    DecisionCorrection,
    DecisionDraft,
)
from apps.api.repositories.decisions import (
    add_correction,
    add_decision,
    add_decision_audit_event,
    add_draft,
    add_snapshot,
    delete_draft,
    get_current_published_version,
    get_decision_for_household,
    get_draft,
    get_household_id,
    get_latest_correction,
    get_policy_for_household,
    get_snapshot,
    list_corrections,
    list_decision_audit_events,
    list_decisions,
    next_correction_number,
)


class HouseholdRequiredError(Exception):
    pass


class DecisionNotFoundError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class DecisionConflictError(Exception):
    pass


class NoDecisionChangesError(Exception):
    pass


class DecisionIncompleteError(Exception):
    pass


class PolicyVersionMismatchError(Exception):
    pass


class DecisionLifecycleError(Exception):
    pass


class PolicyNotFoundError(Exception):
    pass


class PublishedPolicyNotFoundError(Exception):
    pass


def _require_household(session: Session) -> UUID:
    household_id = get_household_id(session)
    if household_id is None:
        raise HouseholdRequiredError
    return household_id


def _require_decision(
    session: Session,
    decision_id: UUID,
    household_id: UUID,
    *,
    for_update: bool = False,
) -> Decision:
    decision = get_decision_for_household(
        session, decision_id, household_id, for_update=for_update
    )
    if decision is None:
        raise DecisionNotFoundError
    return decision


def _require_draft(
    session: Session, decision_id: UUID, *, for_update: bool = False
) -> DecisionDraft:
    draft = get_draft(session, decision_id, for_update=for_update)
    if draft is None:
        raise DraftNotFoundError
    return draft


def _constraint_name(exc: IntegrityError) -> Optional[str]:
    diagnostics = getattr(exc.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


# ---------------------------------------------------------------------------
# Create Decision Draft
# ---------------------------------------------------------------------------


def create_decision(
    session: Session, payload: CreateDecisionRequest
) -> tuple[Decision, DecisionDraft]:
    household_id = _require_household(session)
    try:
        with session.begin():
            decision = add_decision(session, household_id)
            draft = add_draft(session, decision.id, values={"title": payload.title})
            add_decision_audit_event(
                session,
                household_id=household_id,
                decision_id=decision.id,
                action="decision.draft.created",
                metadata={"draft_revision": draft.revision},
            )
        return decision, draft
    except IntegrityError as exc:
        session.rollback()
        if _constraint_name(exc) != "uq_decision_drafts_decision_id":
            raise
        raise DecisionConflictError from exc


# ---------------------------------------------------------------------------
# Decision List
# ---------------------------------------------------------------------------


def read_decision_list(
    session: Session,
    *,
    status_filter: Optional[str] = None,
    include_archived: bool = False,
) -> list[tuple[Decision, Optional[DecisionDraft], Optional[DecisionConfirmedSnapshot]]]:
    household_id = _require_household(session)
    return list_decisions(
        session,
        household_id,
        status_filter=status_filter,
        include_archived=include_archived,
    )


# ---------------------------------------------------------------------------
# Draft Detail
# ---------------------------------------------------------------------------


def read_draft(session: Session, decision_id: UUID) -> DecisionDraft:
    household_id = _require_household(session)
    decision = _require_decision(session, decision_id, household_id)
    if decision.status != "draft":
        raise DraftNotFoundError
    return _require_draft(session, decision_id)


# ---------------------------------------------------------------------------
# Update Draft
# ---------------------------------------------------------------------------


def update_draft(
    session: Session, decision_id: UUID, payload: UpdateDecisionDraftRequest
) -> DecisionDraft:
    household_id = _require_household(session)
    submitted = payload.model_dump(exclude={"expected_revision"}, exclude_unset=True)
    if not submitted:
        raise NoDecisionChangesError

    with session.begin():
        decision = _require_decision(
            session, decision_id, household_id, for_update=True
        )
        if decision.status != "draft":
            raise DecisionLifecycleError
        draft = _require_draft(session, decision_id, for_update=True)
        if draft.revision != payload.expected_revision:
            raise DecisionConflictError

        changed = sorted(
            name
            for name, value in submitted.items()
            if getattr(draft, name) != value
        )
        if not changed:
            raise NoDecisionChangesError

        for name in changed:
            setattr(draft, name, submitted[name])
        draft.revision += 1
        draft.updated_at = datetime.now(timezone.utc)
        session.flush()

        add_decision_audit_event(
            session,
            household_id=household_id,
            decision_id=decision_id,
            action="decision.draft.updated",
            metadata={"changed_fields": changed, "draft_revision": draft.revision},
        )
    return draft


# ---------------------------------------------------------------------------
# Discard Draft
# ---------------------------------------------------------------------------


def discard_draft(
    session: Session, decision_id: UUID, payload: DiscardDecisionRequest
) -> None:
    household_id = _require_household(session)
    with session.begin():
        decision = _require_decision(
            session, decision_id, household_id, for_update=True
        )
        if decision.status != "draft":
            raise DecisionLifecycleError
        draft = _require_draft(session, decision_id, for_update=True)
        if draft.revision != payload.expected_revision:
            raise DecisionConflictError

        # Verify never-Confirmed (no snapshot exists)
        snapshot = get_snapshot(session, decision_id)
        if snapshot is not None:
            raise DecisionLifecycleError

        add_decision_audit_event(
            session,
            household_id=household_id,
            decision_id=decision_id,
            action="decision.draft.discarded",
            metadata={"draft_revision": draft.revision},
        )
        delete_draft(session, draft)
        session.delete(decision)
        session.flush()


# ---------------------------------------------------------------------------
# Confirm Draft
# ---------------------------------------------------------------------------


def confirm_draft(
    session: Session, decision_id: UUID, payload: ConfirmDecisionRequest
) -> DecisionConfirmedSnapshot:
    household_id = _require_household(session)
    try:
        with session.begin():
            # Lock Policy first (OD-S3-5)
            policy = get_policy_for_household(
                session, household_id, for_update=True
            )
            if policy is None:
                raise PolicyNotFoundError
            current_published = get_current_published_version(session, policy.id)
            if current_published is None:
                raise PublishedPolicyNotFoundError

            # Lock Decision and Draft
            decision = _require_decision(
                session, decision_id, household_id, for_update=True
            )
            if decision.status != "draft":
                raise DecisionLifecycleError
            draft = _require_draft(session, decision_id, for_update=True)
            if draft.revision != payload.expected_revision:
                raise DecisionConflictError

            # Validate required fields
            for field_name in CONFIRM_REQUIRED_FIELDS:
                if field_name == "decision_date":
                    if draft.decision_date is None:
                        raise DecisionIncompleteError
                else:
                    value = getattr(draft, field_name, None)
                    if value is None or not str(value).strip():
                        raise DecisionIncompleteError

            # Build snapshot values from draft
            snapshot_values: dict[str, Any] = {}
            for field_name in (
                "title",
                "decision_summary",
                "rationale",
                "alternatives_considered",
                "risks_and_uncertainties",
                "evidence_or_sources",
                "expected_outcome",
                "review_trigger",
                "review_date",
                "decision_date",
                "notes",
            ):
                snapshot_values[field_name] = getattr(draft, field_name)

            snapshot = add_snapshot(
                session,
                decision_id=decision_id,
                selected_policy_version_id=current_published.id,
                values=snapshot_values,
            )

            # Delete draft
            delete_draft(session, draft)

            # Update decision status
            decision.status = "confirmed"
            session.flush()

            add_decision_audit_event(
                session,
                household_id=household_id,
                decision_id=decision_id,
                action="decision.confirmed",
                metadata={
                    "policy_version_number": current_published.version_number,
                },
            )
        return snapshot
    except IntegrityError as exc:
        session.rollback()
        constraint = _constraint_name(exc)
        if constraint in {
            "uq_decision_snapshots_decision_id",
            "uq_decision_drafts_decision_id",
        }:
            raise DecisionConflictError from exc
        raise


# ---------------------------------------------------------------------------
# Decision Detail
# ---------------------------------------------------------------------------


def read_decision_detail(session: Session, decision_id: UUID) -> dict[str, Any]:
    household_id = _require_household(session)
    decision = _require_decision(session, decision_id, household_id)

    result: dict[str, Any] = {
        "id": decision.id,
        "household_id": decision.household_id,
        "status": decision.status,
        "created_at": decision.created_at,
        "archived_at": decision.archived_at,
        "archive_reason": decision.archive_reason,
    }

    if decision.status == "draft":
        draft = get_draft(session, decision_id)
        if draft is not None:
            result["draft"] = draft
        result["original_snapshot"] = None
        result["effective_snapshot"] = None
        result["latest_correction_metadata"] = None
        result["corrections_count"] = 0
        return result

    snapshot = get_snapshot(session, decision_id)
    corrections = list_corrections(session, decision_id)
    latest_correction = get_latest_correction(session, decision_id)

    result["original_snapshot"] = snapshot
    if latest_correction is not None:
        # Build effective snapshot from latest correction
        result["effective_snapshot"] = latest_correction
    else:
        result["effective_snapshot"] = snapshot

    if latest_correction is not None:
        result["latest_correction_metadata"] = {
            "correction_id": latest_correction.id,
            "correction_number": latest_correction.correction_number,
            "created_at": latest_correction.created_at,
            "correction_reason": latest_correction.correction_reason,
        }
    else:
        result["latest_correction_metadata"] = None

    result["corrections_count"] = len(corrections)
    return result


# ---------------------------------------------------------------------------
# Archive / Unarchive
# ---------------------------------------------------------------------------


def archive_decision(
    session: Session, decision_id: UUID, payload: ArchiveDecisionRequest
) -> Decision:
    household_id = _require_household(session)
    with session.begin():
        decision = _require_decision(
            session, decision_id, household_id, for_update=True
        )
        if decision.status != "confirmed":
            raise DecisionLifecycleError
        decision.status = "archived"
        decision.archived_at = datetime.now(timezone.utc)
        decision.archive_reason = payload.archive_reason
        session.flush()
        add_decision_audit_event(
            session,
            household_id=household_id,
            decision_id=decision_id,
            action="decision.archived",
            metadata={},
        )
    return decision


def unarchive_decision(session: Session, decision_id: UUID) -> Decision:
    household_id = _require_household(session)
    with session.begin():
        decision = _require_decision(
            session, decision_id, household_id, for_update=True
        )
        if decision.status != "archived":
            raise DecisionLifecycleError
        decision.status = "confirmed"
        decision.archived_at = None
        decision.archive_reason = None
        session.flush()
        add_decision_audit_event(
            session,
            household_id=household_id,
            decision_id=decision_id,
            action="decision.unarchived",
            metadata={},
        )
    return decision


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------


def append_correction(
    session: Session, decision_id: UUID, payload: AppendCorrectionRequest
) -> DecisionCorrection:
    household_id = _require_household(session)
    try:
        with session.begin():
            decision = _require_decision(
                session, decision_id, household_id, for_update=True
            )
            if decision.status not in ("confirmed", "archived"):
                raise DecisionLifecycleError

            snapshot = get_snapshot(session, decision_id)
            if snapshot is None:
                raise DecisionNotFoundError

            correction_number = next_correction_number(session, decision_id)

            correction_values: dict[str, Any] = {}
            for field_name in (
                "title",
                "decision_summary",
                "rationale",
                "alternatives_considered",
                "risks_and_uncertainties",
                "evidence_or_sources",
                "expected_outcome",
                "review_trigger",
                "review_date",
                "decision_date",
                "notes",
                "correction_reason",
            ):
                correction_values[field_name] = getattr(payload, field_name)

            correction = add_correction(
                session,
                decision_id=decision_id,
                corrected_entry_id=snapshot.id,
                correction_number=correction_number,
                values=correction_values,
            )

            add_decision_audit_event(
                session,
                household_id=household_id,
                decision_id=decision_id,
                action="decision.correction.appended",
                metadata={"correction_number": correction_number},
            )
        return correction
    except IntegrityError as exc:
        session.rollback()
        constraint = _constraint_name(exc)
        if constraint == "uq_decision_corrections_decision_correction_number":
            raise DecisionConflictError from exc
        raise


def read_corrections(
    session: Session, decision_id: UUID
) -> list[DecisionCorrection]:
    household_id = _require_household(session)
    _require_decision(session, decision_id, household_id)
    return list_corrections(session, decision_id)


# ---------------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------------


def read_decision_audit_events(
    session: Session,
    decision_id: UUID,
    *,
    before_sequence_number: Optional[int] = None,
    limit: int = 50,
) -> tuple[list[AuditEvent], Optional[int]]:
    household_id = _require_household(session)
    _require_decision(session, decision_id, household_id)
    return list_decision_audit_events(
        session,
        household_id=household_id,
        decision_id=decision_id,
        before_sequence_number=before_sequence_number,
        limit=limit,
    )
