"""Guardian monitoring API endpoints (Sprint 004 Slice B)."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.guardian_schemas import (
    GuardianCheckConfirm,
    GuardianCheckDetailResponse,
    GuardianCheckDiscard,
    GuardianCheckDraftCreate,
    GuardianCheckDraftResponse,
    GuardianCheckDraftUpdate,
    GuardianCheckIdentityResponse,
    GuardianCheckListResponse,
    GuardianEvaluateRequest,
    GuardianEvaluateResponse,
    GuardianEvaluationRunListResponse,
    GuardianEvaluationRunResponse,
    GuardianEventListResponse,
    GuardianEventResponse,
)
from apps.api.services.guardian import (
    CheckAlreadyConfirmedError,
    CheckNotFoundError,
    CheckNotDraftError,
    ConfirmRequiresDraftError,
    DraftConflictError,
    DraftNotFoundError,
    HouseholdRequiredError,
    InvalidCheckTypeFieldsError,
    NameConflictError,
    ParentDeletedError,
    confirm_guardian_check,
    create_guardian_check,
    discard_guardian_check,
    evaluate_all_checks,
    evaluate_one_check,
    get_check_detail,
    update_guardian_draft,
)
from apps.api.repositories.guardian import (
    get_current_household_id,
    list_checks,
    list_evaluation_runs,
    list_events,
    get_evaluation_run,
    get_events_by_run,
)

router = APIRouter(prefix="/api/guardian", tags=["guardian"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def _get_household(session: Session) -> UUID:
    hid = get_current_household_id(session)
    if hid is None:
        raise HTTPException(status_code=404, detail="Household profile not found")
    return hid


def _translate(exc: Exception) -> HTTPException:
    mapping = {
        HouseholdRequiredError: (404, "Household profile not found"),
        CheckNotFoundError: (404, "Guardian check not found"),
        DraftNotFoundError: (404, "No draft for this check"),
        DraftConflictError: (409, "Draft revision conflict"),
        NameConflictError: (409, "A check with this name already exists"),
        CheckNotDraftError: (409, "Check is not in draft status"),
        CheckAlreadyConfirmedError: (409, "Version already confirmed"),
        ConfirmRequiresDraftError: (422, "Cannot confirm without a draft"),
        InvalidCheckTypeFieldsError: (422, "Invalid check type field combination"),
        ParentDeletedError: (422, "Parent check deleted"),
    }
    for cls, (code, msg) in mapping.items():
        if isinstance(exc, cls):
            return HTTPException(status_code=code, detail=msg)
    return HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Check lifecycle — create, list, read, update, confirm, discard
# ---------------------------------------------------------------------------


@router.post("/checks", status_code=status.HTTP_201_CREATED)
def api_create_check(
    body: GuardianCheckDraftCreate,
    session: DatabaseSession,
) -> GuardianCheckDetailResponse:
    from decimal import Decimal as _D
    hid = _get_household(session)
    try:
        check, draft = create_guardian_check(
            session,
            household_id=hid,
            name=body.name,
            check_type=body.check_type,
            threshold_value=_D(body.threshold_value),
            severity=body.severity,
            target_category=body.target_category,
            target_holding_category=body.target_holding_category,
            staleness_days=body.staleness_days,
            notes=body.notes,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    return _build_detail(check, draft, None)


@router.get("/checks", response_model=GuardianCheckListResponse)
def api_list_checks(session: DatabaseSession) -> GuardianCheckListResponse:
    hid = _get_household(session)
    checks = list_checks(session, hid)
    return GuardianCheckListResponse(
        checks=[GuardianCheckIdentityResponse.model_validate(c) for c in checks]
    )


@router.get("/checks/{check_id}", response_model=GuardianCheckDetailResponse)
def api_get_check(check_id: UUID, session: DatabaseSession) -> GuardianCheckDetailResponse:
    _get_household(session)
    try:
        detail = get_check_detail(session, check_id)
    except Exception as exc:
        raise _translate(exc)
    return _build_detail(
        detail["identity"], detail["draft"], detail["latest_version"],
    )


@router.patch("/checks/{check_id}/draft", response_model=GuardianCheckDetailResponse)
def api_update_draft(
    check_id: UUID,
    body: GuardianCheckDraftUpdate,
    session: DatabaseSession,
) -> GuardianCheckDetailResponse:
    _get_household(session)
    from decimal import Decimal as _D
    try:
        draft = update_guardian_draft(
            session,
            check_id=check_id,
            expected_revision=body.expected_revision,
            threshold_value=_D(body.threshold_value) if body.threshold_value else None,
            target_category=body.target_category,
            target_holding_category=body.target_holding_category,
            staleness_days=body.staleness_days,
            severity=body.severity,
            notes=body.notes,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    detail = get_check_detail(session, check_id)
    return _build_detail(
        detail["identity"], detail["draft"], detail["latest_version"],
    )


@router.post("/checks/{check_id}/confirm", response_model=GuardianCheckDetailResponse)
def api_confirm_check(
    check_id: UUID,
    body: GuardianCheckConfirm,
    session: DatabaseSession,
) -> GuardianCheckDetailResponse:
    _get_household(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        confirm_guardian_check(
            session,
            check_id=check_id,
            expected_revision=body.expected_revision,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    detail = get_check_detail(session, check_id)
    return _build_detail(
        detail["identity"], detail["draft"], detail["latest_version"],
    )


@router.post("/checks/{check_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def api_discard_check(
    check_id: UUID,
    body: GuardianCheckDiscard,
    session: DatabaseSession,
):
    _get_household(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        discard_guardian_check(session, check_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@router.post("/evaluate", response_model=GuardianEvaluateResponse)
def api_evaluate_all(
    body: GuardianEvaluateRequest,
    session: DatabaseSession,
) -> GuardianEvaluateResponse:
    hid = _get_household(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        run = evaluate_all_checks(session, household_id=hid, as_of_date=body.as_of_date)
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    events = get_events_by_run(session, run.id)
    return GuardianEvaluateResponse(
        evaluation_run=GuardianEvaluationRunResponse.model_validate(run),
        events=[GuardianEventResponse.model_validate(e) for e in events],
    )


@router.post("/checks/{check_id}/evaluate", response_model=GuardianEvaluateResponse)
def api_evaluate_one(
    check_id: UUID,
    body: GuardianEvaluateRequest,
    session: DatabaseSession,
) -> GuardianEvaluateResponse:
    hid = _get_household(session)
    if not body.confirmation:
        raise HTTPException(status_code=422, detail="confirmation must be true")
    try:
        run = evaluate_one_check(
            session, check_id=check_id, household_id=hid,
            as_of_date=body.as_of_date,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _translate(exc)
    events = get_events_by_run(session, run.id)
    return GuardianEvaluateResponse(
        evaluation_run=GuardianEvaluationRunResponse.model_validate(run),
        events=[GuardianEventResponse.model_validate(e) for e in events],
    )


# ---------------------------------------------------------------------------
# Read-only history
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=GuardianEvaluationRunListResponse)
def api_list_runs(
    session: DatabaseSession,
    limit: int = Query(50, ge=1, le=200),
) -> GuardianEvaluationRunListResponse:
    hid = _get_household(session)
    runs = list_evaluation_runs(session, hid, limit=limit)
    return GuardianEvaluationRunListResponse(
        runs=[GuardianEvaluationRunResponse.model_validate(r) for r in runs]
    )


@router.get("/runs/{run_id}", response_model=GuardianEvaluateResponse)
def api_get_run(
    run_id: UUID,
    session: DatabaseSession,
) -> GuardianEvaluateResponse:
    _get_household(session)
    run = get_evaluation_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    events = get_events_by_run(session, run_id)
    return GuardianEvaluateResponse(
        evaluation_run=GuardianEvaluationRunResponse.model_validate(run),
        events=[GuardianEventResponse.model_validate(e) for e in events],
    )


@router.get("/events", response_model=GuardianEventListResponse)
def api_list_events(
    session: DatabaseSession,
    limit: int = Query(50, ge=1, le=200),
) -> GuardianEventListResponse:
    hid = _get_household(session)
    events = list_events(session, hid, limit=limit)
    return GuardianEventListResponse(
        events=[GuardianEventResponse.model_validate(e) for e in events]
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from apps.api.guardian_schemas import GuardianCheckConfirmedResponse


def _build_detail(
    identity, draft, latest
) -> GuardianCheckDetailResponse:
    return GuardianCheckDetailResponse(
        identity=GuardianCheckIdentityResponse.model_validate(identity),
        draft=GuardianCheckDraftResponse.model_validate(draft) if draft else None,
        latest_version=GuardianCheckConfirmedResponse.model_validate(latest) if latest else None,
    )
