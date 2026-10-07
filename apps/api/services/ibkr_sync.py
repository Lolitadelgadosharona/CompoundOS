"""Atomic, household-scoped IBKR read ingestion. No strategy/order/quote writes."""

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, text

from apps.api.models import Account, Asset, CashBalance, Position
from apps.api.repositories.portfolios import get_portfolio
from apps.api.services.broker_foundation import (
    BrokerConnection,
    CanonicalResolver,
    StagingStore,
)
from apps.api.services.ibkr_adapter import CAPABILITIES, GatewayUnavailable, configured_provider

SUCCESS = ("CURRENT", "UNRESOLVED")


def schema_available(session):
    return bool(
        session.execute(text("SELECT to_regclass('public.ibkr_read_connections')")).scalar()
    )


def serialize(value):
    return json.dumps(value, default=str)


def latest(session, connection, successful=False):
    clause = " AND status IN ('CURRENT','UNRESOLVED')" if successful else ""
    return (
        session.execute(
            text(
                "SELECT * FROM ibkr_read_sync_runs WHERE connection_id=:c"
                + clause
                + " ORDER BY completed_at DESC,id DESC LIMIT 1"
            ),
            {"c": connection["id"]},
        )
        .mappings()
        .first()
    )


def summary(session, hid):
    """A sanitized view; never makes a gateway call on GET."""
    import os

    empty = {
        "name": "Interactive Brokers",
        "status": "NOT_CONNECTED",
        "mode": "READ_ONLY",
        "connection_type": "NONE",
        "available": os.getenv("COMPOUNDOS_IBKR_READ_ENABLED") == "1",
        "capabilities": [c.value for c in sorted(CAPABILITIES, key=lambda c: c.value)],
        "external_connection": False,
        "last_sync": None,
        "accounts_discovered": 0,
        "cash": None,
        "positions": None,
        "data_quality": "UNKNOWN",
        "unresolved": 0,
        "accounts": [],
        "holdings": [],
        "cash_balances": [],
        "valuation_mode": "NOT_LIVE",
        "recommendation_ready": False,
    }
    if not schema_available(session):
        empty["available"] = False
        return empty
    connection = (
        session.execute(
            text(
                "SELECT * FROM ibkr_read_connections WHERE household_id=:h "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"h": hid},
        )
        .mappings()
        .first()
    )
    if not connection:
        return empty
    run = latest(session, connection)
    successful = latest(session, connection, True)
    payload = successful["snapshot"] if successful else {}
    rows = payload.get("positions", [])
    targets = (
        session.execute(
            text(
                "SELECT settings FROM investment_configurations WHERE household_id=:h "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"h": hid},
        ).scalar()
        or {}
    )
    weights = {t["asset_id"]: t["weight"] for t in targets.get("targets", [])}
    now = datetime.now(timezone.utc)
    status = "CONNECTED" if successful and connection["enabled"] else "NOT_CONNECTED"
    freshness = "UNKNOWN"
    if successful and now - successful["completed_at"] > timedelta(hours=24):
        status, freshness = "STALE", "STALE"
    if run and run["status"] == "SYNC_FAILED":
        status, freshness = "SYNC_FAILED", "SYNC_FAILED"
    for row in payload.get("cash", []):
        observed = datetime.fromisoformat(row["provenance"]["as_of"])
        if now - observed > timedelta(hours=24) and status == "CONNECTED":
            status, freshness = "STALE", "STALE"
    if not connection["enabled"]:
        status, freshness = "DISCONNECTED", "STALE"
    return dict(
        empty,
        status=status,
        connection_type=connection["mode"],
        external_connection=bool(successful),
        last_sync=successful["completed_at"].isoformat() if successful else None,
        last_attempt=run["completed_at"].isoformat() if run else None,
        sync_id=str(run["id"]) if run else None,
        error_code=run["error_code"] if run else None,
        accounts_discovered=len(payload.get("accounts", [])),
        positions=len(rows),
        cash="Native balances; see below" if successful else None,
        data_quality=freshness,
        unresolved=successful["unresolved"] if successful else 0,
        accounts=[
            {
                "reference": "…" + a["external_id"][-4:],
                "currency": a["currency"],
                "source": connection["mode"],
            }
            for a in payload.get("accounts", [])
        ],
        cash_balances=[
            {
                "account": "…" + c["account_ref"][-4:],
                "currency": c["currency"],
                "amount": c["amount"],
                "as_of": c["provenance"]["as_of"],
                "quality": c["provenance"]["quality"],
            }
            for c in payload.get("cash", [])
        ],
        holdings=[
            {
                "account": "…" + p["account_ref"][-4:],
                "symbol": payload["details"].get(p["external_id"], {}).get("symbol") or "Unknown",
                "conid": payload["details"].get(p["external_id"], {}).get("conid"),
                "quantity": p["quantity"],
                "currency": p["currency"],
                "average_cost": payload["details"].get(p["external_id"], {}).get("average_cost"),
                "canonical_id": p["canonical_id"],
                "identity_status": p["status"],
                "target": str(weights.get(p["canonical_id"], "0")),
                "non_target": p["canonical_id"] not in weights,
                "quality": p["provenance"]["quality"],
                "source": connection["mode"],
            }
            for p in rows
        ],
        available=empty["available"],
    )


def trust_state(session, hid):
    """Persisted broker observations block new recommendations even if connector is disabled."""
    if not schema_available(session):
        return None
    connections = (
        session.execute(
            text("SELECT * FROM ibkr_read_connections WHERE household_id=:h"), {"h": hid}
        )
        .mappings()
        .all()
    )
    for c in connections:
        if latest(session, c):
            return {
                "broker_data": c["mode"],
                "market_data": "SEPARATE",
                "status": "NOT_LIVE",
                "recommendation_ready": False,
            }
    return None


def publish_ledger(session, hid, connection, snapshot, details, run_id):
    portfolio = get_portfolio(session, hid)
    if not portfolio:
        raise GatewayUnavailable("IBKR_MANUAL_PORTFOLIO_SETUP_REQUIRED")
    account_ids = {}
    provider = "interactive_brokers:" + connection["mode"].lower()
    for record in snapshot.accounts:
        # Global legacy provider uniqueness is preserved; never adopt another owner's account.
        account = session.scalar(
            select(Account).where(
                Account.provider == provider, Account.provider_account_id == record.external_id
            )
        )
        if account and account.portfolio_id != portfolio.id:
            raise GatewayUnavailable("IBKR_ACCOUNT_OWNERSHIP_CONFLICT")
        if not account:
            account = Account(
                id=uuid4(),
                portfolio_id=portfolio.id,
                name="IBKR " + connection["mode"] + " …" + record.external_id[-4:],
                account_type="brokerage",
                capital_bucket="OTHER",
                currency=record.currency,
                provider=provider,
                provider_account_id=record.external_id,
            )
            session.add(account)
            session.flush()
        elif account.currency != record.currency:
            raise GatewayUnavailable("IBKR_ACCOUNT_CURRENCY_CHANGED")
        account_ids[record.external_id] = account.id
    previous_accounts = list(
        session.scalars(
            select(Account.id).where(
                Account.portfolio_id == portfolio.id, Account.provider == provider
            )
        )
    )
    # Only this household/provider's prior observations; manual/DEMO rows remain untouched.
    for model in (Position, CashBalance):
        session.execute(
            model.__table__.update()
            .where(
                model.account_id.in_(previous_accounts),
                model.source == "interactive_brokers",
                model.is_latest.is_(True),
            )
            .values(is_latest=False)
        )
    for record in snapshot.positions:
        if record.canonical_id is None:
            raise GatewayUnavailable("IBKR_UNRESOLVED_BATCH")
        d = details[record.external_id]
        session.add(
            Position(
                id=uuid4(),
                account_id=account_ids[record.account_ref],
                asset_id=record.canonical_id,
                quantity=record.quantity,
                quantity_source="provider_reported",
                avg_cost=d["average_cost"],
                avg_cost_currency=record.currency,
                avg_cost_source="IBKR_REPORTED_AVERAGE_COST",
                market_price=None,
                market_price_currency=record.currency,
                market_value=None,
                market_value_currency=record.currency,
                cost_basis=None,
                cost_basis_currency=record.currency,
                observed_at=record.provenance.as_of,
                source="interactive_brokers",
                source_record_id=str(connection["id"])
                + ":"
                + str(run_id)
                + ":"
                + record.external_id,
            )
        )
    for record in snapshot.cash:
        session.add(
            CashBalance(
                id=uuid4(),
                account_id=account_ids[record.account_ref],
                currency=record.currency,
                amount=record.amount,
                observed_at=record.provenance.as_of,
                source="interactive_brokers",
                source_record_id=str(connection["id"])
                + ":"
                + str(run_id)
                + ":"
                + record.external_id,
            )
        )
    session.flush()


def sync(session, hid, provider=None):
    from apps.api.services.launch_investment import audit, lock_household

    """Owner action only. Complete transaction incl resolver, ledger, sync history and audit."""
    # Injection used only by isolated tests; public API never accepts provider/URL/headers.
    public_request = provider is None
    provider = provider or configured_provider()
    if not schema_available(session):
        raise GatewayUnavailable("IBKR_LOCAL_MIGRATION_REQUIRED")
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('ibkr-local-gateway-read',0))")
    )
    lock_household(session, hid)
    if public_request:
        import time

        previous_attempt = session.execute(
            text("SELECT max(started_at) FROM ibkr_read_sync_runs")
        ).scalar()
        if previous_attempt:
            time.sleep(max(0, 5 - (datetime.now(timezone.utc) - previous_attempt).total_seconds()))
    connection = (
        session.execute(
            text("SELECT * FROM ibkr_read_connections WHERE household_id=:h AND mode=:m"),
            {"h": hid, "m": provider.mode},
        )
        .mappings()
        .first()
    )
    if not connection:
        cid = uuid4()
        session.execute(
            text("INSERT INTO ibkr_read_connections(id,household_id,mode) VALUES(:i,:h,:m)"),
            {"i": cid, "h": hid, "m": provider.mode},
        )
        connection = {"id": cid, "mode": provider.mode, "enabled": True}
    if not connection["enabled"]:
        # An explicit next Sync action reconnects; no automatic polling/reconnect.
        session.execute(
            text("UPDATE ibkr_read_connections SET enabled=true WHERE id=:c"),
            {"c": connection["id"]},
        )
    previous_run = latest(session, connection, True)
    started, run_id = datetime.now(timezone.utc), uuid4()
    received = accepted = unresolved = 0
    payload, error_code, status = {}, None, "SYNC_FAILED"
    try:
        with session.begin_nested():
            result = provider.read_result()
            if result.mode != connection["mode"]:
                raise GatewayUnavailable("IBKR_ACCOUNT_MODE_MISMATCH")
            snap = result.snapshot
            received = len(snap.accounts) + len(snap.positions) + len(snap.cash)
            if previous_run:
                for kind in ("accounts", "positions", "cash"):
                    old = {r["external_id"]: r for r in previous_run["snapshot"].get(kind, [])}
                    for record in getattr(snap, kind):
                        former = old.get(record.external_id)
                        if former and record.provenance.as_of < datetime.fromisoformat(
                            former["provenance"]["as_of"]
                        ):
                            raise GatewayUnavailable("IBKR_OUT_OF_ORDER_SNAPSHOT")
            store = StagingStore()
            resolver = CanonicalResolver(session)

            # Existing canonical classification may refine IBKR's broad STK class.
            def resolve(instrument):
                matches = list(
                    session.scalars(
                        select(Asset).where(
                            Asset.symbol == instrument.symbol,
                            Asset.currency == instrument.currency,
                            Asset.exchange == instrument.exchange,
                        )
                    )
                )
                if len(matches) == 1 and matches[0].asset_type in {"ETF", "STOCK"}:
                    instrument = replace(instrument, asset_type=matches[0].asset_type)
                with session.begin_nested():
                    return resolver(instrument)

            domain_connection = BrokerConnection(
                hid, connection["id"], "interactive_brokers", provider.capabilities
            )
            run = store.sync(domain_connection, snap, resolve, datetime.now(timezone.utc))
            if run.status == "SYNC_FAILED":
                raise GatewayUnavailable("IBKR_NORMALIZATION_FAILED")
            normalized = store.view(domain_connection, datetime.now(timezone.utc))["snapshot"]
            accepted, unresolved = run.accepted, run.unresolved
            payload = {**asdict(normalized), "details": result.details, "mode": provider.mode}
            status = run.status
            # Unknown records stay visible; incomplete batches do not replace the ledger.
            if not unresolved:
                publish_ledger(session, hid, connection, normalized, result.details, run_id)
    except Exception as exc:
        status, accepted, unresolved, payload = "SYNC_FAILED", 0, 0, {}
        error_code = str(exc) if isinstance(exc, GatewayUnavailable) else "IBKR_SYNC_FAILED"
        import re

        if not re.fullmatch(r"IBKR_[A-Z0-9_]{1,70}", error_code):
            error_code = "IBKR_SYNC_FAILED"
    completed = datetime.now(timezone.utc)
    session.execute(
        text("""INSERT INTO ibkr_read_sync_runs
        (id,connection_id,started_at,completed_at,status,received,accepted,unresolved,error_code,snapshot)
        VALUES(:i,:c,:s,:e,:t,:r,:a,:u,:err,CAST(:p AS jsonb))"""),
        {
            "i": run_id,
            "c": connection["id"],
            "s": started,
            "e": completed,
            "t": status,
            "r": received,
            "a": accepted,
            "u": unresolved,
            "err": error_code,
            "p": serialize(payload),
        },
    )
    audit(
        session,
        hid,
        "ibkr.read.sync",
        run_id,
        {
            "status": status,
            "mode": provider.mode,
            "received": received,
            "accepted": accepted,
            "unresolved": unresolved,
            "execution_allowed": False,
        },
    )
    session.commit()
    return summary(session, hid)


def disconnect(session, hid):
    from apps.api.services.launch_investment import audit, lock_household

    if schema_available(session):
        lock_household(session, hid)
        session.execute(
            text("UPDATE ibkr_read_connections SET enabled=false WHERE household_id=:h"), {"h": hid}
        )
        audit(session, hid, "ibkr.read.disconnected", hid, {"execution_allowed": False})
        session.commit()
    return summary(session, hid)
