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
    create_asset,
    create_cash_balance,
    create_position,
    find_asset_by_identity,
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
    """Aggregate wealth by asset_type + cash + capital bucket. Read-only."""
    household = _household(session)
    portfolio = get_portfolio(session, household.id)
    if portfolio is None:
        return {
            "net_worth": None, "stocks": None, "etf": None, "bonds": None,
            "cash": None, "other": None,
            "capital_bucket_summary": [], "last_updated": None,
        }

    type_rows = session.execute(text(
        "SELECT COALESCE(ast.asset_type, 'OTHER'),"
        " COALESCE(SUM(p.market_value), 0)"
        " FROM positions p"
        " JOIN accounts a ON p.account_id = a.id"
        " JOIN assets ast ON p.asset_id = ast.id"
        " WHERE a.portfolio_id = :pid AND p.is_latest = TRUE"
        " GROUP BY ast.asset_type"
    ), {"pid": portfolio.id}).fetchall()

    cash_total = session.execute(text(
        "SELECT COALESCE(SUM(cb.amount), 0)"
        " FROM cash_balances cb"
        " JOIN accounts a ON cb.account_id = a.id"
        " WHERE a.portfolio_id = :pid AND cb.is_latest = TRUE"
    ), {"pid": portfolio.id}).scalar() or Decimal("0")

    bucket_rows = session.execute(text(
        "SELECT a.capital_bucket,"
        " COALESCE(SUM(p.market_value), 0),"
        " COALESCE(SUM(cb.amount), 0)"
        " FROM accounts a"
        " LEFT JOIN positions p ON p.account_id = a.id AND p.is_latest = TRUE"
        " LEFT JOIN cash_balances cb ON cb.account_id = a.id AND cb.is_latest = TRUE"
        " WHERE a.portfolio_id = :pid"
        " GROUP BY a.capital_bucket"
    ), {"pid": portfolio.id}).fetchall()

    last_updated = session.execute(text(
        "SELECT MAX(observed_at) FROM ("
        "  SELECT observed_at FROM positions p"
        "   JOIN accounts a ON p.account_id = a.id"
        "   WHERE a.portfolio_id = :pid AND p.is_latest = TRUE"
        "  UNION ALL"
        "  SELECT observed_at FROM cash_balances cb"
        "   JOIN accounts a ON cb.account_id = a.id"
        "   WHERE a.portfolio_id = :pid AND cb.is_latest = TRUE"
        ") sub"
    ), {"pid": portfolio.id}).scalar()

    stocks = etf = bonds = other = position_cash = Decimal("0")
    for asset_type, value in type_rows:
        value = value or Decimal("0")
        if asset_type == "STOCK":
            stocks += value
        elif asset_type == "ETF":
            etf += value
        elif asset_type == "BOND":
            bonds += value
        elif asset_type in ("CASH", "MONEY_MARKET"):
            position_cash += value
        else:
            other += value

    cash = position_cash + cash_total
    net_worth = stocks + etf + bonds + other + cash

    return {
        "net_worth": _money(net_worth) if net_worth else None,
        "stocks": _money(stocks) if stocks else None,
        "etf": _money(etf) if etf else None,
        "bonds": _money(bonds) if bonds else None,
        "cash": _money(cash) if cash else None,
        "other": _money(other) if other else None,
        "capital_bucket_summary": [
            {
                "bucket": bucket,
                "value": _money((pos_value or Decimal("0"))
                               + (cash_value or Decimal("0"))),
            }
            for bucket, pos_value, cash_value in bucket_rows
        ],
        "last_updated": str(last_updated) if last_updated else None,
    }


def list_accounts(session: Session, household_id: UUID) -> list[dict]:
    household = _household(session)
    portfolio = get_portfolio(session, household.id)
    if portfolio is None:
        return []
    return [
        {
            "id": str(a.id), "name": a.name, "account_type": a.account_type,
            "provider": a.provider, "currency": a.currency,
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
    rows = session.execute(text(
        "SELECT a.name, ast.symbol, ast.asset_type, p.quantity,"
        " p.avg_cost, p.market_value, p.source"
        " FROM positions p"
        " JOIN accounts a ON p.account_id = a.id"
        " JOIN assets ast ON p.asset_id = ast.id"
        " WHERE a.portfolio_id = :pid AND p.is_latest = TRUE"
        " ORDER BY ast.symbol"
    ), {"pid": portfolio.id}).fetchall()
    return [
        {
            "account_name": r[0], "symbol": r[1] or "?",
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
    rows = session.execute(text(
        "SELECT a.name, cb.currency, cb.amount, cb.source"
        " FROM cash_balances cb"
        " JOIN accounts a ON cb.account_id = a.id"
        " WHERE a.portfolio_id = :pid AND cb.is_latest = TRUE"
        " ORDER BY cb.currency"
    ), {"pid": portfolio.id}).fetchall()
    return [
        {
            "account_name": r[0], "currency": r[1],
            "amount": _money(r[2]) if r[2] is not None else None,
            "source": r[3],
        }
        for r in rows
    ]


# ── Writes ──────────────────────────────────────────────────────────────


def add_account(
    session: Session, *, name: str, account_type: str, capital_bucket: str,
    currency: str, provider: str | None = None,
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
            "id": str(account.id), "name": account.name,
            "account_type": account.account_type,
            "capital_bucket": account.capital_bucket,
            "currency": account.currency,
            "provider": account.provider,
        }


def add_holding(
    session: Session, *, account_id: UUID, symbol: str, asset_type: str,
    quantity: Decimal, avg_cost: Decimal, currency: str = "USD",
) -> dict:
    with session.begin():
        _household(session)
        asset = find_asset_by_identity(session, symbol, None, currency)
        if asset is None:
            asset = create_asset(
                session,
                symbol=symbol, name=symbol, asset_type=asset_type,
                currency=currency, exchange=None,
            )
        supersede_latest_positions(session, account_id, asset.id)
        now = datetime.now(timezone.utc)
        quantity_d = Decimal(str(quantity))
        avg_cost_d = Decimal(str(avg_cost))
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
            "id": str(position.id), "symbol": symbol, "asset_type": asset_type,
            "quantity": _money(quantity_d), "avg_cost": _money(avg_cost_d),
            "source": MANUAL_SOURCE,
        }


def add_cash(
    session: Session, *, account_id: UUID, currency: str, amount: Decimal,
) -> dict:
    with session.begin():
        _household(session)
        supersede_latest_cash_balances(session, account_id, currency)
        now = datetime.now(timezone.utc)
        amount_d = Decimal(str(amount))
        balance = create_cash_balance(
            session,
            account_id=account_id,
            currency=currency,
            amount=amount_d,
            observed_at=now,
            source=MANUAL_SOURCE,
        )
        return {
            "id": str(balance.id), "currency": currency,
            "amount": _money(amount_d), "source": MANUAL_SOURCE,
        }
