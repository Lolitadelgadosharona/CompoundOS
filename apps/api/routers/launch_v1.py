"""Owner-only V1 routes. All mutations reuse existing financial lifecycles."""

from dataclasses import asdict
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services import launch_investment as svc
from apps.api.services.backtest_boundary import availability as backtest_availability
from apps.api.services.instrument_resolver import InstrumentUnavailable, canonical_asset
from apps.api.services.launch_providers import get_instrument_provider
from apps.api.services.valuation import RecommendationUnavailable, load_valuation

router = APIRouter(prefix="/api/investment", tags=["investment-v1"])


def household(session):
    hid = get_household_id(session)
    if not hid:
        raise HTTPException(404, "Configure household first")
    return hid


def guarded(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RecommendationUnavailable as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, InstrumentUnavailable) as exc:
        raise HTTPException(422, str(exc)) from exc


class Target(BaseModel):
    asset_id: UUID
    weight: Decimal = Field(gt=0, le=100)
    leverage_status: Literal["unleveraged", "leveraged", "unknown"] = "unknown"
    equity_exposure_pct: Decimal | None = Field(default=None, ge=0, le=100)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_currency: str = Field(pattern="^[A-Z]{3}$")
    monthly_currency: str = Field(pattern="^[A-Z]{3}$")
    monthly_amount: Decimal = Field(ge=0)
    initial_capital: Decimal = Field(ge=0)
    targets: list[Target] = Field(min_length=1, max_length=30)


class Selection(BaseModel):
    provider_id: str = Field(min_length=1, max_length=30)


class Holding(BaseModel):
    account_id: UUID
    asset_id: UUID
    quantity: Decimal = Field(ge=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)
    cost_currency: str = Field(pattern="^[A-Z]{3}$")


@router.get("/instruments")
def search(q: str = Query(min_length=1, max_length=200)):
    return {
        "candidates": [asdict(i) for i in guarded(get_instrument_provider().search, q)],
        "provider": get_instrument_provider().name,
        "selection_required": True,
    }


@router.post("/instruments", status_code=201)
def select_instrument(body: Selection, session: Session = Depends(get_session)):
    household(session)
    provider = get_instrument_provider()
    instrument = guarded(provider.identify, body.provider_id)
    asset = guarded(canonical_asset, session, instrument)
    session.commit()
    return {"asset_id": str(asset.id), **asdict(instrument)}


@router.post("/holdings", status_code=201)
def holding(body: Holding, session: Session = Depends(get_session)):
    from datetime import datetime, timezone

    from apps.api.models import Asset
    from apps.api.repositories.portfolio_foundation import (
        create_position,
        supersede_latest_positions,
    )
    from apps.api.services.portfolio_reality import _require_owned_account

    hid = household(session)
    guarded(_require_owned_account, session, body.account_id)
    asset = session.get(Asset, body.asset_id)
    if not asset:
        raise HTTPException(422, "Canonical instrument not found")
    supersede_latest_positions(session, body.account_id, asset.id)
    position = create_position(
        session,
        account_id=body.account_id,
        asset_id=asset.id,
        quantity=body.quantity,
        quantity_source="provider_reported",
        avg_cost=body.avg_cost,
        avg_cost_currency=body.cost_currency,
        market_price=None,
        market_price_currency=asset.currency,
        market_value=None,
        market_value_currency=asset.currency,
        cost_basis=body.quantity * body.avg_cost if body.avg_cost is not None else None,
        cost_basis_currency=body.cost_currency,
        observed_at=datetime.now(timezone.utc),
        source="manual",
    )
    svc.audit(
        session,
        hid,
        "contribution.holding.recorded",
        position.id,
        {"asset_id": str(asset.id), "quantity": str(body.quantity)},
    )
    session.commit()
    return {
        "id": str(position.id),
        "asset_id": str(asset.id),
        "status": "native_ledger_recorded",
        "quote_required": True,
    }


@router.get("/configuration")
def get_configuration(session: Session = Depends(get_session)):
    row = guarded(svc.configuration, session, household(session))
    return {
        "id": str(row["id"]),
        "policy_version_id": str(row["policy_version_id"]),
        **row["settings"],
    }


@router.post("/configuration", status_code=201)
def save_configuration(body: Settings, session: Session = Depends(get_session)):
    return guarded(svc.configure, session, household(session), body.model_dump(mode="json"))


@router.post("/refresh")
def refresh(session: Session = Depends(get_session)):
    return guarded(svc.refresh_data, session, household(session))


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    hid = household(session)
    v = load_valuation(session, hid)
    from apps.api.services.portfolio_reality import list_accounts, list_cash

    rows = (
        session.execute(
            text(
                (
                    "SELECT id FROM contribution_candidates WHERE household_id=:h ORDER BY "
                    "created_at DESC LIMIT 10"
                )
            ),
            {"h": hid},
        )
        .scalars()
        .all()
    )
    candidates = [svc.candidate_detail(session, hid, c) for c in rows]
    entries = []
    exposures = {}
    for e in v.entries:
        value = e.get("base_value")
        weight = value / v.total() * 100 if value is not None and v.total() else None
        native_cost = e.get("cost_basis")
        gain = (
            e.get("native_value") - native_cost
            if e.get("native_value") is not None
            and native_cost is not None
            and e.get("cost_basis_currency") == e.get("currency")
            else None
        )
        entries.append(
            {
                "id": str(e["id"]),
                "asset_id": str(e.get("asset_id") or ""),
                "symbol": e.get("symbol") or e["currency"],
                "kind": e["kind"],
                "value": str(value) if value is not None else None,
                "weight": str(weight) if weight is not None else None,
                "gain_loss_native": str(gain) if gain is not None else None,
                "currency": e["currency"],
                "quality": e["quality_status"],
            }
        )
        if value is not None:
            exposures[e["currency"]] = str(Decimal(exposures.get(e["currency"], "0")) + value)
    config = None
    try:
        c = svc.configuration(session, hid)
        config = {"id": str(c["id"]), **c["settings"]}
        config["targets"] = [
            {**asdict(svc.mapped_instrument(session, UUID(t["asset_id"]))), **t}
            for t in config["targets"]
        ]
    except RecommendationUnavailable:
        pass
    return {
        "valuation": v.contract(),
        "cash_value": str(v.total("cash")) if v.total("cash") is not None else None,
        "positions": entries,
        "currency_exposure": exposures if not v.reasons else None,
        "configuration": config,
        "accounts": list_accounts(session, hid),
        "cash": list_cash(session, hid),
        "candidates": candidates,
        "execution": "MANUAL",
        "backtest": backtest_availability(),
    }


class CandidateRequest(BaseModel):
    funding: Literal["monthly", "initial"] = "monthly"


@router.post("/candidates", status_code=201)
def candidate(body: CandidateRequest = CandidateRequest(), session: Session = Depends(get_session)):
    return guarded(svc.make_candidate, session, household(session), body.funding)


@router.get("/candidates/{cid}")
def detail(cid: UUID, session: Session = Depends(get_session)):
    return guarded(svc.candidate_detail, session, household(session), cid)


@router.post("/candidates/{cid}/committee-preview")
def preview(cid: UUID, session: Session = Depends(get_session)):
    return guarded(svc.preview_committee, session, household(session), cid)


class CommitteeConsent(BaseModel):
    confirmation: bool
    content_hash: str


@router.post("/candidates/{cid}/committee")
def committee(cid: UUID, body: CommitteeConsent, session: Session = Depends(get_session)):
    hid = household(session)
    row = guarded(svc.validate_candidate, session, hid, cid)
    if (
        not body.confirmation
        or body.content_hash != row["content_hash"]
        or not row.get("committee_session_id")
    ):
        raise HTTPException(409, "Preview exact evidence and confirm provider disclosure first")
    from apps.api.models import CommitteeSession
    from apps.api.services.ai_provider import DeepSeekProvider
    from apps.api.services.committee_orchestration import run_committee
    from apps.api.services.credential_manager import CredentialError

    cs = session.get(CommitteeSession, UUID(row["committee_session_id"]), with_for_update=True)
    if cs.status != "draft":
        raise HTTPException(409, "Committee already requested; no duplicate provider call")
    cs.status = "queued"
    session.commit()
    try:
        run_committee(
            session, cs, DeepSeekProvider(), prompt_version="contribution-v1", max_retries=0
        )
    except (ValueError, RuntimeError, CredentialError) as exc:
        raise HTTPException(
            503, "Committee unavailable or output rejected; approval remains blocked"
        ) from exc
    svc.audit(
        session, hid, "contribution.committee.completed", cid, {"content_hash": row["content_hash"]}
    )
    session.commit()
    return svc.candidate_detail(session, hid, cid)


@router.post("/candidates/{cid}/approve")
def approve(cid: UUID, session: Session = Depends(get_session)):
    return guarded(svc.approve, session, household(session), cid)


@router.post("/candidates/{cid}/reject")
def reject(cid: UUID, session: Session = Depends(get_session)):
    hid = household(session)
    svc.lock_household(session, hid)
    row = guarded(svc.candidate_detail, session, hid, cid)
    # Append rejection to Audit; never erase evidence/linked Journal drafts.
    if row.get("decision_status") in {"confirmed", "archived"}:
        raise HTTPException(409, "Decision already confirmed")
    existing = session.execute(
        text("SELECT 1 FROM audit_events WHERE entity_id=:i AND action='contribution.rejected'"),
        {"i": cid},
    ).scalar()
    if existing:
        raise HTTPException(409, "Already rejected")
    svc.audit(
        session,
        hid,
        "contribution.rejected",
        cid,
        {"decision_id": row.get("decision_id"), "evidence_hash": row["content_hash"]},
    )
    session.commit()
    return {"status": "rejected", "execution": "NONE"}
