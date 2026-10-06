"""Personal Edition portfolio reality service (PE-003A).

Read/write Richard's REAL holdings (Account / Position / CashBalance /
Asset) — not the portfolio draft/snapshot "plan" model. Read-only queries
never fabricate data; empty portfolios surface None/"Not configured".
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.repositories.households import get_current_household
from apps.api.repositories.portfolio_foundation import (
    create_account as _create_account,
)
from apps.api.repositories.portfolio_foundation import (
    create_cash_balance,
    create_position,
    supersede_latest_cash_balances,
    supersede_latest_positions,
)
from apps.api.repositories.portfolio_foundation import (
    list_accounts as _list_accounts,
)
from apps.api.repositories.portfolios import get_portfolio

MANUAL_SOURCE = "manual"


class HouseholdNotFoundError(ValueError):
    pass


def _household(session: Session):
    household = get_current_household(session)
    if household is None:
        raise HouseholdNotFoundError("Household profile not found")
    return household


def _ensure_portfolio(session: Session):
    """Ensure portfolio + draft exist (draft status requires a draft row).

    Reuses the existing draft/snapshot lifecycle's read_or_create_portfolio
    so the portfolio consistency trigger is satisfied.
    """
    from apps.api.services.portfolios import (
        HouseholdRequiredError,
        read_or_create_portfolio,
    )

    try:
        portfolio, _draft, _holdings, _created = read_or_create_portfolio(session)
    except HouseholdRequiredError as exc:
        raise HouseholdNotFoundError(str(exc)) from exc
    return portfolio


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))


# ── Reads ───────────────────────────────────────────────────────────────


def wealth_summary(session: Session, household_id: UUID) -> dict:
    """Common valuation; positions and cash are loaded independently."""
    from apps.api.services.valuation import load_valuation

    v = load_valuation(session, household_id)
    categories = {k: Decimal(0) for k in ("stocks", "etf", "bonds", "cash", "other")}
    buckets = {}
    if not v.reasons:
        for e in v.entries:
            category = (
                "cash"
                if e["kind"] == "cash"
                else {
                    "STOCK": "stocks",
                    "ETF": "etf",
                    "BOND": "bonds",
                    "CASH": "cash",
                    "MONEY_MARKET": "cash",
                }.get(e.get("asset_type"), "other")
            )
            categories[category] += e["base_value"]
            bucket = e.get("capital_bucket") or "Other"
            buckets[bucket] = buckets.get(bucket, Decimal(0)) + e["base_value"]
    return {
        "net_worth": _money(v.total()) if v.total() is not None and v.entries else None,
        **{k: _money(n) if not v.reasons and n else None for k, n in categories.items()},
        "capital_bucket_summary": [{"bucket": k, "value": _money(n)} for k, n in buckets.items()],
        "last_updated": v.as_of.isoformat(),
        **v.contract(),
    }


def list_accounts(session: Session, household_id: UUID) -> list[dict]:
    household = _household(session)
    portfolio = get_portfolio(session, household.id)
    if portfolio is None:
        return []
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "account_type": a.account_type,
            "provider": a.provider,
            "currency": a.currency,
            "capital_bucket": a.capital_bucket,
            "source": a.provider or MANUAL_SOURCE,
        }
        for a in _list_accounts(session, portfolio.id)
    ]


def list_holdings(session: Session, household_id: UUID) -> list[dict]:
    household = _household(session)
    portfolio = get_portfolio(session, household.id)
    if portfolio is None:
        return []
    rows = session.execute(
        text(
            "SELECT a.name, ast.symbol, ast.asset_type, p.quantity,"
            " p.avg_cost, p.market_value, p.source"
            " FROM positions p"
            " JOIN accounts a ON p.account_id = a.id"
            " JOIN assets ast ON p.asset_id = ast.id"
            " WHERE a.portfolio_id = :pid AND p.is_latest = TRUE"
            " ORDER BY ast.symbol"
        ),
        {"pid": portfolio.id},
    ).fetchall()
    return [
        {
            "account_name": r[0],
            "symbol": r[1] or "?",
            "asset_type": r[2],
            "quantity": _money(r[3]) if r[3] is not None else None,
            "avg_cost": _money(r[4]) if r[4] is not None else None,
            "market_value": _money(r[5]) if r[5] is not None else None,
            "source": r[6],
        }
        for r in rows
    ]


def list_cash(session: Session, household_id: UUID) -> list[dict]:
    household = _household(session)
    portfolio = get_portfolio(session, household.id)
    if portfolio is None:
        return []
    rows = session.execute(
        text(
            "SELECT a.name, cb.currency, cb.amount, cb.source"
            " FROM cash_balances cb"
            " JOIN accounts a ON cb.account_id = a.id"
            " WHERE a.portfolio_id = :pid AND cb.is_latest = TRUE"
            " ORDER BY cb.currency"
        ),
        {"pid": portfolio.id},
    ).fetchall()
    return [
        {
            "account_name": r[0],
            "currency": r[1],
            "amount": _money(r[2]) if r[2] is not None else None,
            "source": r[3],
        }
        for r in rows
    ]


# ── Writes ──────────────────────────────────────────────────────────────


def add_account(
    session: Session,
    *,
    name: str,
    account_type: str,
    capital_bucket: str,
    currency: str,
    provider: str | None = None,
) -> dict:
    portfolio = _ensure_portfolio(session)
    with session.begin():
        account = _create_account(
            session,
            portfolio_id=portfolio.id,
            name=name,
            account_type=account_type,
            capital_bucket=capital_bucket,
            currency=currency,
            provider=provider,
        )
        return {
            "id": str(account.id),
            "name": account.name,
            "account_type": account.account_type,
            "capital_bucket": account.capital_bucket,
            "currency": account.currency,
            "provider": account.provider,
        }


def add_holding(
    session: Session,
    *,
    account_id: UUID,
    symbol: str,
    asset_type: str,
    quantity: Decimal,
    avg_cost: Decimal,
    currency: str = "USD",
) -> dict:
    with session.begin():
        _household(session)
        from apps.api.services.instrument_resolver import ledger_identity

        asset = ledger_identity(session, symbol, currency=currency, asset_type=asset_type)
        _require_owned_account(session, account_id)
        supersede_latest_positions(session, account_id, asset.id)
        now = datetime.now(timezone.utc)
        quantity_d = Decimal(str(quantity))
        avg_cost_d = Decimal(str(avg_cost))
        if (
            not quantity_d.is_finite()
            or not avg_cost_d.is_finite()
            or quantity_d < 0
            or avg_cost_d < 0
        ):
            raise ValueError("Quantity/cost must be finite and nonnegative")
        position = create_position(
            session,
            account_id=account_id,
            asset_id=asset.id,
            quantity=quantity_d,
            quantity_source="provider_reported",
            avg_cost=avg_cost_d,
            avg_cost_currency=currency,
            market_price=avg_cost_d,
            market_price_currency=currency,
            market_value=quantity_d * avg_cost_d,
            market_value_currency=currency,
            cost_basis=quantity_d * avg_cost_d,
            cost_basis_currency=currency,
            observed_at=now,
            source=MANUAL_SOURCE,
        )
        return {
            "id": str(position.id),
            "symbol": symbol,
            "asset_type": asset_type,
            "quantity": _money(quantity_d),
            "avg_cost": _money(avg_cost_d),
            "source": MANUAL_SOURCE,
        }


def add_cash(
    session: Session,
    *,
    account_id: UUID,
    currency: str,
    amount: Decimal,
) -> dict:
    with session.begin():
        _household(session)
        _require_owned_account(session, account_id)
        supersede_latest_cash_balances(session, account_id, currency)
        now = datetime.now(timezone.utc)
        amount_d = Decimal(str(amount))
        if not amount_d.is_finite() or amount_d < 0:
            raise ValueError("Cash must be finite and nonnegative")
        balance = create_cash_balance(
            session,
            account_id=account_id,
            currency=currency,
            amount=amount_d,
            observed_at=now,
            source=MANUAL_SOURCE,
        )
        return {
            "id": str(balance.id),
            "currency": currency,
            "amount": _money(amount_d),
            "source": MANUAL_SOURCE,
        }


def _require_owned_account(session, account_id):
    hid = _household(session).id
    from apps.api.services.launch_investment import lock_household

    lock_household(session, hid)
    owned = session.execute(
        text("""SELECT a.id FROM accounts a JOIN portfolios p ON p.id=a.portfolio_id
        WHERE a.id=:id AND p.household_id=:hid"""),
        {"id": account_id, "hid": hid},
    ).scalar()
    if not owned:
        raise ValueError("Account not found for household")
