"""Guardian monitoring API endpoints (Sprint 004 Slice B)."""

from __future__ import annotations

from decimal import Decimal as _Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.guardian_schemas import (
    GuardianCheckConfirm,
    GuardianCheckDetailResponse,
    GuardianCheckDiscard,
    GuardianCheckDraftCreate,
    GuardianCheckDraftUpdate,
    GuardianCheckListResponse,
    GuardianEvaluateRequest,
    GuardianEvaluateResponse,
    GuardianEvaluationRunListResponse,
    GuardianEvaluationRunResponse,
    GuardianEventListResponse,
    GuardianEventResponse,
)
from apps.api.services.guardian import (
    CheckNotFoundError,
    ConfirmRequiresDraftError,
    DraftConflictError,
    DraftNotFoundError,
    HouseholdRequiredError,
    InvalidCheckTypeFieldsError,
    NameConflictError,
    confirm_guardian_check,
    create_guardian_check,
    discard_guardian_check,
    evaluate_all_checks,
    evaluate_one_check,
    update_guardian_draft,
)
from apps.api.repositories.guardian import (
    get_current_household_id,
    get_check,
    get_draft,
    get_latest_confirmed_version,
    list_checks,
    list_evaluation_runs,
    list_events,
    get_evaluation_run,
    get_events_by_run,
)

router = APIRouter(prefix="/api/guardian", tags=["guardian"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def _hid(session: Session) -> str:
    row = session.execute(
        text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Household profile not found")
    return str(row[0])


from sqlalchemy import text


def _translate(exc: Exception) -> HTTPException:
    mapping = {
        HouseholdRequiredError: (404, "Household profile not found"),
        CheckNotFoundError: (404, "Guardian check not found"),
        DraftNotFoundError: (404, "No draft for this check"),
        DraftConflictError: (409, "Draft revision conflict"),
        NameConflictError: (409, "A check with this name already exists"),
        InvalidCheckTypeFieldsError: (422, "Invalid check type field combination"),
        ConfirmRequiresDraftError: (422, "Cannot confirm without a draft"),
    }
    for cls, (code, msg) in mapping.items():
        if isinstance(exc, cls):
            return HTTPException(status_code=code, detail=msg)
    return HTTPException(status_code=500, detail="Internal server error")


def _build_detail(identity: dict, draft: dict, latest: dict) -> dict:
    return {
        "identity": identity,
        "draft": draft,
        "latest_version": latest,
    }


# ---------------------------------------------------------------------------
# Check lifecycle
# ---------------------------------------------------------------------------


@router.post("/checks", status_code=status.HTTP_201_CREATED)
def api_create_check(
    body: GuardianCheckDraftCreate,
    session: DatabaseSession,
):
    hid = _hid(session)
    try:
        result = create_guardian_check(
            session,
            household_id=UUID(hid),
            name=body.name,
            check_type=body.check_type,
            threshold_value=_Decimal(body.threshold_value),
            severity=body.severity,
            target_category=body.target_category,
            target_holding_category=body.target_holding_category,
            staleness_days=body.staleness_days,
            notes=body.notes,
        )
    except Exception as exc:
        raise _translate(exc)
    return _build_detail(**result)


@router.get("/checks")
def api_list_checks(session: DatabaseSession) -> GuardianCheckListResponse:
    hid = _hid(session)
    checks = list_checks(session, UUID(hid))
    return GuardianCheckListResponse(
        checks=[{"id": c.id, "household_id": c.household_id,
                 "name": c.name, "canonical_name": c.canonical_name,
                 "check_type": c.check_type, "status": c.status,
                 "created_at": c.created_at, "updated_at": c.updated_at}
                for c in checks]
    )


@router.get("/checks/{check_id}")
def api_get_check(check_id: UUID, session: DatabaseSession):
    _hid(session)
    from apps.api.services.guardian import get_check_detail
    try:
        result = get_check_detail(session, check_id)
    except Exception as exc:
        raise _translate(exc)
    return _build_detail(**result)


def get_check_detail(session: Session, check_id: UUID) -> dict:
    from apps.api.services.guardian import _load_check_detail
    return _load_check_detail(session, check_id)


@router.patch("/checks/{check_id}/draft")
def api_update_draft(
    check_id: UUID,
    body: GuardianCheckDraftUpdate,
    session: DatabaseSession,
):
    _hid(session)
    try:
        result = update_guardian_draft(
            session,
            check_id=check_id,
            expected_revision=body.expected_revision,
            threshold_value=_Decimal(body.threshold_value) if body.threshold_value else None,
            target_category=body.target_category,
            target_holding_category=body.target_holding_category,
            staleness_days=body.staleness_days,
            severity=body.severity,
            notes=body.notes,
        )
    except Exception as exc:
        raise _translate(exc)
    return _build_detail(**result)


@router.post("/checks/{check_id}/confirm")
def api_confirm_check(
    check_id: UUID,
    body: GuardianCheckConfirm,
    session: DatabaseSession,
):
    _hid(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        result = confirm_guardian_check(
            session, check_id=check_id,
            expected_revision=body.expected_revision,
        )
    except Exception as exc:
        raise _translate(exc)
    return _build_detail(**result)


@router.post("/checks/{check_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def api_discard_check(
    check_id: UUID,
    body: GuardianCheckDiscard,
    session: DatabaseSession,
):
    _hid(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        discard_guardian_check(session, check_id)
    except Exception as exc:
        raise _translate(exc)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@router.post("/evaluate")
def api_evaluate_all(
    body: GuardianEvaluateRequest,
    session: DatabaseSession,
):
    hid = _hid(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        result = evaluate_all_checks(
            session, household_id=UUID(hid),
            as_of_date=body.as_of_date,
        )
    except Exception as exc:
        raise _translate(exc)
    return result


@router.post("/checks/{check_id}/evaluate")
def api_evaluate_one(
    check_id: UUID,
    body: GuardianEvaluateRequest,
    session: DatabaseSession,
):
    hid = _hid(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        result = evaluate_one_check(
            session, check_id=check_id,
            household_id=UUID(hid),
            as_of_date=body.as_of_date,
        )
    except Exception as exc:
        raise _translate(exc)
    return result


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/runs")
def api_list_runs(
    session: DatabaseSession,
    limit: int = Query(50, ge=1, le=200),
):
    hid = _hid(session)
    runs = list_evaluation_runs(session, UUID(hid), limit=limit)
    return {
        "runs": [
            {
                "id": str(r.id), "household_id": str(r.household_id),
                "status": r.status, "skip_reason": r.skip_reason,
                "checks_evaluated": r.checks_evaluated,
                "events_created": r.events_created,
                "as_of_date": str(r.as_of_date) if r.as_of_date else None,
                "created_at": r.created_at,
            }
            for r in runs
        ]
    }


@router.get("/runs/{run_id}")
def api_get_run(run_id: UUID, session: DatabaseSession):
    _hid(session)
    run = get_evaluation_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    events = get_events_by_run(session, run_id)
    return {
        "evaluation_run": {
            "id": str(run.id), "household_id": str(run.household_id),
            "status": run.status, "skip_reason": run.skip_reason,
            "checks_evaluated": run.checks_evaluated,
            "events_created": run.events_created,
            "as_of_date": str(run.as_of_date) if run.as_of_date else None,
            "created_at": run.created_at,
        },
        "events": [
            {
                "id": str(e.id), "evaluation_run_id": str(e.evaluation_run_id),
                "check_id": str(e.check_id),
                "check_version_id": str(e.check_version_id),
                "check_type": e.check_type,
                "policy_version_id": str(e.policy_version_id),
                "portfolio_snapshot_id": str(e.portfolio_snapshot_id),
                "exceeded": e.exceeded,
                "drift_pp": str(e.drift_pp) if e.drift_pp else None,
                "exposure_pct": str(e.exposure_pct) if e.exposure_pct else None,
                "staleness_days_actual": e.staleness_days_actual,
                "as_of_date": str(e.as_of_date) if e.as_of_date else None,
                "detected_at": e.detected_at,
            }
            for e in events
        ],
    }


@router.get("/events")
def api_list_events(
    session: DatabaseSession,
    limit: int = Query(50, ge=1, le=200),
):
    hid = _hid(session)
    events = list_events(session, UUID(hid), limit=limit)
    return {
        "events": [
            {
                "id": str(e.id), "evaluation_run_id": str(e.evaluation_run_id),
                "check_id": str(e.check_id),
                "check_version_id": str(e.check_version_id),
                "check_type": e.check_type,
                "policy_version_id": str(e.policy_version_id),
                "portfolio_snapshot_id": str(e.portfolio_snapshot_id),
                "exceeded": e.exceeded,
                "drift_pp": str(e.drift_pp) if e.drift_pp else None,
                "exposure_pct": str(e.exposure_pct) if e.exposure_pct else None,
                "staleness_days_actual": e.staleness_days_actual,
                "as_of_date": str(e.as_of_date) if e.as_of_date else None,
                "detected_at": e.detected_at,
            }
            for e in events
        ]
    }
