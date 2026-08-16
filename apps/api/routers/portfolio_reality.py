"""Personal Edition portfolio reality API (PE-003A).

Owner-only write endpoints for manual account / holding / cash entry.
Read endpoints expose Richard's real wealth (no fabricated values).
No broker APIs, no credentials stored.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services import portfolio_reality

router = APIRouter(prefix="/api/portfolio", tags=["portfolio-reality"])


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    account_type: str = "brokerage"
    capital_bucket: str = "CORE"
    currency: str = "USD"
    provider: str | None = None


class HoldingCreate(BaseModel):
    account_id: UUID
    symbol: str = Field(min_length=1, max_length=20)
    asset_type: str
    quantity: str
    avg_cost: str
    currency: str = "USD"


class CashCreate(BaseModel):
    account_id: UUID
    currency: str
    amount: str


def _household_id(session: Session) -> UUID:
    hid = get_household_id(session)
    if hid is None:
        raise HTTPException(404, "Household profile not found")
    return hid


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, portfolio_reality.HouseholdNotFoundError):
        return HTTPException(404, str(exc))
    return HTTPException(400, str(exc))


@router.get("/wealth")
def wealth(session: Session = Depends(get_session)):
    return portfolio_reality.wealth_summary(session, _household_id(session))


@router.get("/accounts")
def accounts(session: Session = Depends(get_session)):
    return {"accounts": portfolio_reality.list_accounts(session, _household_id(session))}


@router.get("/holdings")
def holdings(session: Session = Depends(get_session)):
    return {"holdings": portfolio_reality.list_holdings(session, _household_id(session))}


@router.get("/cash")
def cash(session: Session = Depends(get_session)):
    return {"cash": portfolio_reality.list_cash(session, _household_id(session))}


@router.post("/accounts", status_code=201)
def create_account(payload: AccountCreate,
                   session: Session = Depends(get_session)):
    try:
        return portfolio_reality.add_account(
            session, name=payload.name, account_type=payload.account_type,
            capital_bucket=payload.capital_bucket, currency=payload.currency,
            provider=payload.provider,
        )
    except Exception as exc:  # noqa: BLE001 — API boundary
        raise _translate(exc) from exc


@router.post("/holdings", status_code=201)
def create_holding(payload: HoldingCreate,
                   session: Session = Depends(get_session)):
    try:
        return portfolio_reality.add_holding(
            session, account_id=payload.account_id, symbol=payload.symbol,
            asset_type=payload.asset_type, quantity=payload.quantity,
            avg_cost=payload.avg_cost, currency=payload.currency,
        )
    except Exception as exc:  # noqa: BLE001 — API boundary
        raise _translate(exc) from exc


@router.post("/cash", status_code=201)
def create_cash(payload: CashCreate,
                session: Session = Depends(get_session)):
    try:
        return portfolio_reality.add_cash(
            session, account_id=payload.account_id, currency=payload.currency,
            amount=payload.amount,
        )
    except Exception as exc:  # noqa: BLE001 — API boundary
        raise _translate(exc) from exc
