from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    Portfolio,
    PortfolioDraft,
    PortfolioDraftHolding,
    PortfolioSnapshot,
    PortfolioSnapshotHolding,
)
from apps.api.portfolio_schemas import (
    ConfirmDraftRequest,
    DiscardDraftRequest,
    HoldingInput,
    HoldingResponse,
    HoldingsReplaceRequest,
    PortfolioDraftResponse,
    PortfolioDraftUpdate,
    PortfolioSnapshotDetail,
)
from apps.api.repositories.households import get_current_household
from apps.api.repositories.portfolios import (
    add_draft,
    add_portfolio,
    add_portfolio_audit_event,
    get_current_snapshot,
    get_draft,
    get_latest_snapshot,
    get_portfolio,
    get_snapshot_by_id,
    has_any_snapshot,
    list_draft_holdings,
    list_portfolio_audit_events,
    list_snapshot_holdings,
    list_snapshots,
    next_version_number,
    replace_draft_holdings,
)

# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class PortfolioError(Exception):
    pass


class HouseholdRequiredError(PortfolioError):
    pass


class PortfolioNotFoundError(PortfolioError):
    pass


class PortfolioAlreadyExistsError(PortfolioError):
    pass


class DraftNotFoundError(PortfolioError):
    pass


class DraftConflictError(PortfolioError):
    pass


class NoChangesError(PortfolioError):
    pass


class SnapshotNotFoundError(PortfolioError):
    pass


class InvalidCashUnitPriceError(PortfolioError):
    """Cash holdings must have unit_price = 1.00 (OD-S3-012)."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _constraint_name(exc: IntegrityError) -> Optional[str]:
    diagnostics = getattr(exc.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def _require_household(
    session: Session, *, for_update: bool = False
):
    household = get_current_household(session, for_update=for_update)
    if household is None:
        raise HouseholdRequiredError
    return household


def _require_portfolio(
    session: Session, household_id: UUID, *, for_update: bool = False
) -> Portfolio:
    portfolio = get_portfolio(session, household_id, for_update=for_update)
    if portfolio is None:
        raise PortfolioNotFoundError
    return portfolio


def _require_draft(
    session: Session, portfolio_id: UUID, *, for_update: bool = False
) -> PortfolioDraft:
    draft = get_draft(session, portfolio_id, for_update=for_update)
    if draft is None:
        raise DraftNotFoundError
    return draft


def _compute_total_value(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def _holding_values(holding: HoldingInput, sort_order: int) -> dict:
    quantity = Decimal(holding.quantity)
    unit_price = Decimal(holding.unit_price)
    total_value = _compute_total_value(quantity, unit_price)
    return {
        "asset_name": holding.asset_name,
        "asset_category": holding.asset_category,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_value": total_value,
        "valuation_date": holding.valuation_date,
        "notes": holding.notes or None,
        "sort_order": sort_order,
    }


def _draft_response(
    draft: PortfolioDraft, holdings: list[PortfolioDraftHolding]
) -> PortfolioDraftResponse:
    return PortfolioDraftResponse(
        portfolio_id=draft.portfolio_id,
        expected_revision=draft.expected_revision,
        valuation_date=draft.valuation_date,
        notes=draft.notes,
        updated_at=draft.updated_at,
        holdings=[HoldingResponse.model_validate(h) for h in holdings],
    )


def _snapshot_detail_response(
    snapshot: PortfolioSnapshot, holdings: list[PortfolioSnapshotHolding]
) -> PortfolioSnapshotDetail:
    return PortfolioSnapshotDetail(
        id=snapshot.id,
        portfolio_id=snapshot.portfolio_id,
        version_number=snapshot.version_number,
        status=snapshot.status,
        confirmed_at=snapshot.confirmed_at,
        holding_count=snapshot.holding_count,
        valuation_date=snapshot.valuation_date,
        notes=snapshot.notes,
        holdings=[HoldingResponse.model_validate(h) for h in holdings],
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def read_or_create_portfolio(
    session: Session,
) -> tuple[Portfolio, PortfolioDraft, list[PortfolioDraftHolding], bool]:
    """Get existing portfolio+draft, or create them in a single transaction.

    Lock order: Household → Portfolio → Draft (via FOR UPDATE).
    Returns (portfolio, draft, holdings, created).
    """
    with session.begin():
        household = _require_household(session, for_update=True)
        existing = get_portfolio(session, household.id, for_update=True)
        if existing is not None:
            draft = get_draft(session, existing.id, for_update=True)
            if draft is not None:
                holdings = list_draft_holdings(session, existing.id)
                return existing, draft, holdings, False

            # Portfolio exists but no draft (e.g., after confirm).
            # active → draft transition (0004 fn_portfolio_lifecycle allows this).
            # Deferred trigger needs draft status to match draft existence at COMMIT.
            existing.status = "draft"
            draft = add_draft(session, existing.id)
            add_portfolio_audit_event(
                session,
                household_id=household.id,
                portfolio_id=existing.id,
                action="portfolio.draft.created",
                metadata={"draft_revision": draft.expected_revision},
            )
            return existing, draft, [], True

        # No portfolio — create one (household-level serialization
        # via UNIQUE constraint on portfolios.household_id).
        portfolio = add_portfolio(session, household.id)
        draft = add_draft(session, portfolio.id)
        add_portfolio_audit_event(
            session,
            household_id=household.id,
            portfolio_id=portfolio.id,
            action="portfolio.draft.created",
            metadata={"draft_revision": draft.expected_revision},
        )
        return portfolio, draft, [], True


def read_current_state(
    session: Session,
) -> tuple[
    Optional[PortfolioDraft],
    list[PortfolioDraftHolding],
    Optional[PortfolioSnapshot],
    Optional[list[PortfolioSnapshotHolding]],
]:
    """Return current draft + holdings (may be None), and latest snapshot + holdings."""
    household = _require_household(session)
    portfolio = _require_portfolio(session, household.id)
    draft = get_draft(session, portfolio.id)
    draft_holdings = (
        list_draft_holdings(session, portfolio.id) if draft is not None else []
    )
    latest = get_latest_snapshot(session, portfolio.id)
    snapshot_holdings = None
    if latest is not None:
        snapshot_holdings = list_snapshot_holdings(session, latest.id)
    return draft, draft_holdings, latest, snapshot_holdings


def update_draft(
    session: Session, payload: PortfolioDraftUpdate
) -> PortfolioDraftResponse:
    with session.begin():
        household = _require_household(session)
        portfolio = _require_portfolio(session, household.id, for_update=True)
        draft = _require_draft(session, portfolio.id, for_update=True)
        if draft.expected_revision != payload.expected_revision:
            raise DraftConflictError

        changed: list[str] = []
        if (
            payload.valuation_date is not None
            and draft.valuation_date != payload.valuation_date
        ):
            draft.valuation_date = payload.valuation_date
            changed.append("valuation_date")
        if payload.notes is not None and draft.notes != payload.notes:
            draft.notes = payload.notes
            changed.append("notes")

        if not changed:
            raise NoChangesError

        draft.expected_revision += 1
        draft.updated_at = datetime.now(timezone.utc)
        session.flush()
        add_portfolio_audit_event(
            session,
            household_id=household.id,
            portfolio_id=portfolio.id,
            action="portfolio.draft.updated",
            metadata={
                "changed_fields": changed,
                "draft_revision": draft.expected_revision,
            },
        )
        holdings = list_draft_holdings(session, portfolio.id)
        response = _draft_response(draft, holdings)
    return response


def replace_holdings(
    session: Session, payload: HoldingsReplaceRequest
) -> PortfolioDraftResponse:
    with session.begin():
        household = _require_household(session)
        portfolio = _require_portfolio(session, household.id, for_update=True)
        draft = _require_draft(session, portfolio.id, for_update=True)
        if draft.expected_revision != payload.expected_revision:
            raise DraftConflictError

        existing = list_draft_holdings(session, portfolio.id)
        values = [
            _holding_values(item, sort_order)
            for sort_order, item in enumerate(payload.items)
        ]

        # Cash holdings must have unit_price = 1.00 (OD-S3-012)
        for v in values:
            if v["asset_category"].strip().lower() == "cash" and v["unit_price"] != Decimal("1.00"):
                raise InvalidCashUnitPriceError

        # Idempotency check
        existing_sig = [
            (
                h.asset_name,
                h.asset_category,
                h.quantity,
                h.unit_price,
                h.valuation_date,
                h.notes,
                h.sort_order,
            )
            for h in existing
        ]
        proposed_sig = [
            (
                v["asset_name"],
                v["asset_category"],
                v["quantity"],
                v["unit_price"],
                v["valuation_date"],
                v.get("notes"),
                v["sort_order"],
            )
            for v in values
        ]
        if existing_sig == proposed_sig:
            raise NoChangesError

        holdings = replace_draft_holdings(session, portfolio.id, values)
        draft.expected_revision += 1
        draft.updated_at = datetime.now(timezone.utc)
        session.flush()
        add_portfolio_audit_event(
            session,
            household_id=household.id,
            portfolio_id=portfolio.id,
            action="portfolio.draft.updated",
            metadata={
                "changed_fields": ["holdings"],
                "draft_revision": draft.expected_revision,
                "holding_count": len(holdings),
            },
        )
        response = _draft_response(draft, holdings)
    return response


def confirm_draft(
    session: Session, payload: ConfirmDraftRequest
) -> PortfolioSnapshotDetail:
    with session.begin():
        household = _require_household(session)
        portfolio = _require_portfolio(session, household.id, for_update=True)
        draft = _require_draft(session, portfolio.id, for_update=True)
        if draft.expected_revision != payload.expected_revision:
            raise DraftConflictError

        draft_holdings = list_draft_holdings(session, portfolio.id)
        holding_count = len(draft_holdings)

        version_number = next_version_number(session, portfolio.id)

        # Supersede prior current snapshot (0006 allows status-only UPDATE)
        current_snap = get_current_snapshot(session, portfolio.id)
        if current_snap is not None:
            current_snap.status = "superseded"
            session.flush()

        now = datetime.now(timezone.utc)
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            version_number=version_number,
            status="current",
            confirmed_at=now,
            holding_count=holding_count,
            valuation_date=draft.valuation_date or date.today(),
            notes=draft.notes,
        )
        session.add(snapshot)
        session.flush()

        snapshot_holdings: list[PortfolioSnapshotHolding] = []
        for h in draft_holdings:
            snapshot_holdings.append(
                PortfolioSnapshotHolding(
                    snapshot_id=snapshot.id,
                    asset_name=h.asset_name,
                    asset_category=h.asset_category,
                    quantity=h.quantity,
                    unit_price=h.unit_price,
                    total_value=h.total_value,
                    valuation_date=h.valuation_date,
                    notes=h.notes,
                    sort_order=h.sort_order,
                )
            )
        session.add_all(snapshot_holdings)
        session.flush()

        # Delete draft and draft holdings
        session.delete(draft)
        portfolio.status = "active"
        session.flush()

        add_portfolio_audit_event(
            session,
            household_id=household.id,
            portfolio_id=portfolio.id,
            action="portfolio.snapshot.confirmed",
            metadata={
                "snapshot_version_number": snapshot.version_number,
                "holding_count": holding_count,
            },
        )
        response = _snapshot_detail_response(snapshot, snapshot_holdings)
    return response


def discard_draft(
    session: Session, payload: DiscardDraftRequest
) -> Optional[PortfolioSnapshotDetail]:
    with session.begin():
        household = _require_household(session)
        portfolio = _require_portfolio(session, household.id, for_update=True)
        draft = _require_draft(session, portfolio.id, for_update=True)
        if draft.expected_revision != payload.expected_revision:
            raise DraftConflictError

        revision = draft.expected_revision
        any_snapshot = has_any_snapshot(session, portfolio.id)

        if not any_snapshot:
            # Scenario (a): No prior snapshots — delete the entire portfolio
            session.delete(draft)
            session.delete(portfolio)
            session.flush()
            add_portfolio_audit_event(
                session,
                household_id=household.id,
                portfolio_id=portfolio.id,
                action="portfolio.draft.discarded",
                metadata={"draft_revision": revision},
            )
            return None

        # Scenario (b): Confirmed snapshots exist — discard draft only.
        # Set status to 'active' since draft is deleted and snapshots exist.
        portfolio.status = "active"
        session.delete(draft)
        session.flush()
        add_portfolio_audit_event(
            session,
            household_id=household.id,
            portfolio_id=portfolio.id,
            action="portfolio.draft.discarded",
            metadata={"draft_revision": revision},
        )
        # Return the latest snapshot
        latest = get_latest_snapshot(session, portfolio.id)
        if latest is not None:
            snapshot_holdings = list_snapshot_holdings(session, latest.id)
            return _snapshot_detail_response(latest, snapshot_holdings)
    return None


def read_snapshots(
    session: Session,
    *,
    before_version_number: Optional[int],
    limit: int,
) -> tuple[list[PortfolioSnapshot], Optional[int]]:
    household = _require_household(session)
    portfolio = _require_portfolio(session, household.id)
    return list_snapshots(
        session,
        portfolio.id,
        before_version_number=before_version_number,
        limit=limit,
    )


def read_snapshot_detail(
    session: Session, snapshot_id: UUID
) -> tuple[PortfolioSnapshot, list[PortfolioSnapshotHolding]]:
    household = _require_household(session)
    portfolio = _require_portfolio(session, household.id)
    snapshot = get_snapshot_by_id(session, snapshot_id)
    if snapshot is None or snapshot.portfolio_id != portfolio.id:
        raise SnapshotNotFoundError
    return snapshot, list_snapshot_holdings(session, snapshot.id)


def read_audit_events(
    session: Session,
    *,
    before_sequence_number: Optional[int],
    limit: int,
) -> tuple[list[AuditEvent], Optional[int]]:
    household = _require_household(session)
    portfolio = _require_portfolio(session, household.id)
    return list_portfolio_audit_events(
        session,
        household_id=household.id,
        portfolio_id=portfolio.id,
        before_sequence_number=before_sequence_number,
        limit=limit,
    )
