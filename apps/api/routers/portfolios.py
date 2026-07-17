from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.portfolio_schemas import (
    ConfirmDraftRequest,
    DiscardDraftRequest,
    EmptyPortfolioCreateRequest,
    HoldingResponse,
    HoldingsReplaceRequest,
    PortfolioAuditEventResponse,
    PortfolioCreateResponse,
    PortfolioDraftResponse,
    PortfolioDraftUpdate,
    PortfolioResponse,
    PortfolioSnapshotDetail,
    PortfolioSnapshotHistoryResponse,
    PortfolioSnapshotSummary,
)
from apps.api.services.portfolios import (
    DraftConflictError,
    DraftNotFoundError,
    HouseholdRequiredError,
    NoChangesError,
    PortfolioAlreadyExistsError,
    PortfolioNotFoundError,
    SnapshotNotFoundError,
    confirm_draft,
    discard_draft,
    read_audit_events,
    read_current_state,
    read_or_create_portfolio,
    read_snapshot_detail,
    read_snapshots,
    replace_holdings,
    update_draft,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, HouseholdRequiredError):
        return HTTPException(status_code=404, detail="Household profile not found")
    if isinstance(exc, PortfolioNotFoundError):
        return HTTPException(status_code=404, detail="Portfolio not found")
    if isinstance(exc, DraftNotFoundError):
        return HTTPException(status_code=404, detail="Portfolio draft not found")
    if isinstance(exc, SnapshotNotFoundError):
        return HTTPException(status_code=404, detail="Portfolio snapshot not found")
    if isinstance(exc, PortfolioAlreadyExistsError):
        return HTTPException(status_code=409, detail="A portfolio already exists")
    if isinstance(exc, DraftConflictError):
        return HTTPException(
            status_code=409, detail="Portfolio draft changed or unavailable"
        )
    if isinstance(exc, NoChangesError):
        return HTTPException(status_code=400, detail="No portfolio changes provided")
    raise exc


def _holding_responses(holdings) -> list[HoldingResponse]:
    """Convert ORM holding objects to response models."""
    return [HoldingResponse.model_validate(h) for h in holdings]


# ---------------------------------------------------------------------------
# Create / Get portfolio
# ---------------------------------------------------------------------------


@router.post("", response_model=PortfolioCreateResponse, status_code=status.HTTP_201_CREATED)
def create(
    session: DatabaseSession,
    _payload: EmptyPortfolioCreateRequest = Body(default_factory=EmptyPortfolioCreateRequest),
) -> PortfolioCreateResponse:
    try:
        portfolio, draft, holdings, _created = read_or_create_portfolio(session)
        return PortfolioCreateResponse(
            portfolio=PortfolioResponse.model_validate(portfolio),
            draft=PortfolioDraftResponse(
                portfolio_id=draft.portfolio_id,
                expected_revision=draft.expected_revision,
                valuation_date=draft.valuation_date,
                notes=draft.notes,
                updated_at=draft.updated_at,
                holdings=_holding_responses(holdings),
            ),
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("")
def get_current(session: DatabaseSession) -> dict:
    try:
        draft, draft_holdings, latest, snapshot_holdings_list = read_current_state(session)
        result: dict = {
            "portfolio": {"status": "active" if latest else "draft"},
        }
        if draft is not None:
            result["draft"] = PortfolioDraftResponse(
                portfolio_id=draft.portfolio_id,
                expected_revision=draft.expected_revision,
                valuation_date=draft.valuation_date,
                notes=draft.notes,
                updated_at=draft.updated_at,
                holdings=_holding_responses(draft_holdings),
            )
        if latest is not None:
            result["latest_snapshot"] = PortfolioSnapshotDetail(
                id=latest.id,
                portfolio_id=latest.portfolio_id,
                version_number=latest.version_number,
                status=latest.status,
                confirmed_at=latest.confirmed_at,
                holding_count=latest.holding_count,
                valuation_date=latest.valuation_date,
                notes=latest.notes,
                holdings=_holding_responses(snapshot_holdings_list or []),
            )
        return result
    except Exception as exc:
        raise _translate(exc) from exc


# ---------------------------------------------------------------------------
# Draft endpoints
# ---------------------------------------------------------------------------


@router.patch("/draft", response_model=PortfolioDraftResponse)
def patch_draft(
    payload: PortfolioDraftUpdate, session: DatabaseSession
) -> PortfolioDraftResponse:
    try:
        return update_draft(session, payload)
    except Exception as exc:
        raise _translate(exc) from exc


@router.put("/draft/holdings", response_model=PortfolioDraftResponse)
def put_holdings(
    payload: HoldingsReplaceRequest, session: DatabaseSession
) -> PortfolioDraftResponse:
    try:
        return replace_holdings(session, payload)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/draft/confirm",
    response_model=PortfolioSnapshotDetail,
    status_code=status.HTTP_201_CREATED,
)
def confirm(payload: ConfirmDraftRequest, session: DatabaseSession) -> PortfolioSnapshotDetail:
    try:
        return confirm_draft(session, payload)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/draft/discard")
def discard(
    payload: DiscardDraftRequest, session: DatabaseSession
):
    try:
        result = discard_draft(session, payload)
        if result is not None:
            return result
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate(exc) from exc


# ---------------------------------------------------------------------------
# Snapshot endpoints
# ---------------------------------------------------------------------------


@router.get("/snapshots", response_model=PortfolioSnapshotHistoryResponse)
def get_snapshots(
    session: DatabaseSession,
    before_version_number: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> PortfolioSnapshotHistoryResponse:
    try:
        snapshots, next_cursor = read_snapshots(
            session,
            before_version_number=before_version_number,
            limit=limit,
        )
        return PortfolioSnapshotHistoryResponse(
            items=[PortfolioSnapshotSummary.model_validate(s) for s in snapshots],
            next_before_version_number=next_cursor,
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/snapshots/{snapshot_id}", response_model=PortfolioSnapshotDetail)
def get_snapshot(
    snapshot_id: UUID, session: DatabaseSession
) -> PortfolioSnapshotDetail:
    try:
        snapshot, holdings = read_snapshot_detail(session, snapshot_id)
        return PortfolioSnapshotDetail(
            id=snapshot.id,
            portfolio_id=snapshot.portfolio_id,
            version_number=snapshot.version_number,
            status=snapshot.status,
            confirmed_at=snapshot.confirmed_at,
            holding_count=snapshot.holding_count,
            valuation_date=snapshot.valuation_date,
            notes=snapshot.notes,
            holdings=_holding_responses(holdings),
        )
    except Exception as exc:
        raise _translate(exc) from exc


# ---------------------------------------------------------------------------
# Audit endpoint
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=list[PortfolioAuditEventResponse])
def get_audit_events(
    session: DatabaseSession,
    before_sequence_number: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PortfolioAuditEventResponse]:
    try:
        events, _next_cursor = read_audit_events(
            session,
            before_sequence_number=before_sequence_number,
            limit=limit,
        )
        return [PortfolioAuditEventResponse.model_validate(e) for e in events]
    except Exception as exc:
        raise _translate(exc) from exc
