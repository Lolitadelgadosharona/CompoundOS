"""Repository layer for Sprint 009 Slice A — Core Portfolio Foundation.

SQLAlchemy queries for assets, positions, cash balances, transactions,
fx rates, data sources, and extended accounts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.models import (
    Account,
    Asset,
    CashBalance,
    DataSource,
    FxRate,
    Position,
    Transaction,
)

# ═══════════════════════════════════════════════════════════════════════
# Assets
# ═══════════════════════════════════════════════════════════════════════


def get_asset(session: Session, asset_id: UUID, *, for_update: bool = False) -> Optional[Asset]:
    statement = select(Asset).where(Asset.id == asset_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def find_asset_by_isin(session: Session, isin: str) -> Optional[Asset]:
    return session.scalar(select(Asset).where(Asset.isin == isin))


def find_asset_by_identity(
    session: Session, symbol: str, exchange: str, currency: str,
) -> Optional[Asset]:
    return session.scalar(
        select(Asset).where(
            Asset.symbol == symbol,
            Asset.exchange == exchange,
            Asset.currency == currency,
        )
    )


def create_asset(session: Session, **kwargs) -> Asset:
    asset = Asset(id=uuid4(), **kwargs)
    session.add(asset)
    session.flush()
    return asset


def list_assets(session: Session, *, asset_type: Optional[str] = None) -> list[Asset]:
    statement = select(Asset).order_by(Asset.name.asc())
    if asset_type is not None:
        statement = statement.where(Asset.asset_type == asset_type)
    return list(session.scalars(statement))


# ═══════════════════════════════════════════════════════════════════════
# Accounts (extended)
# ═══════════════════════════════════════════════════════════════════════


def get_account(
    session: Session, account_id: UUID, *, for_update: bool = False,
) -> Optional[Account]:
    statement = select(Account).where(Account.id == account_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def update_account_fields(session: Session, account_id: UUID, **fields) -> Optional[Account]:
    """Atomically update nullable fields on an account, returns the refreshed row."""
    account = get_account(session, account_id, for_update=True)
    if account is None:
        return None
    for key, value in fields.items():
        if hasattr(account, key):
            setattr(account, key, value)
    session.flush()
    return account


# ═══════════════════════════════════════════════════════════════════════
# Positions
# ═══════════════════════════════════════════════════════════════════════


def get_position(
    session: Session, position_id: UUID, *, for_update: bool = False,
) -> Optional[Position]:
    statement = select(Position).where(Position.id == position_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_position(session: Session, **kwargs) -> Position:
    position = Position(id=uuid4(), **kwargs)
    session.add(position)
    session.flush()
    return position


def supersede_latest_positions(
    session: Session, account_id: UUID, asset_id: UUID,
) -> None:
    """Set is_latest=False for all currently-latest positions for this account+asset."""
    session.execute(
        update(Position)
        .where(
            Position.account_id == account_id,
            Position.asset_id == asset_id,
            Position.is_latest == True,  # noqa: E712
        )
        .values(is_latest=False)
    )


def list_latest_positions(
    session: Session, account_id: Optional[UUID] = None,
) -> list[Position]:
    statement = (
        select(Position)
        .where(Position.is_latest == True)  # noqa: E712
        .order_by(Position.account_id, Position.asset_id)
    )
    if account_id is not None:
        statement = statement.where(Position.account_id == account_id)
    return list(session.scalars(statement))


# ═══════════════════════════════════════════════════════════════════════
# Cash Balances
# ═══════════════════════════════════════════════════════════════════════


def create_cash_balance(session: Session, **kwargs) -> CashBalance:
    entry = CashBalance(id=uuid4(), **kwargs)
    session.add(entry)
    session.flush()
    return entry


def supersede_latest_cash_balances(
    session: Session, account_id: UUID, currency: str,
) -> None:
    session.execute(
        update(CashBalance)
        .where(
            CashBalance.account_id == account_id,
            CashBalance.currency == currency,
            CashBalance.is_latest == True,  # noqa: E712
        )
        .values(is_latest=False)
    )


def list_latest_cash_balances(
    session: Session, account_id: Optional[UUID] = None,
) -> list[CashBalance]:
    statement = (
        select(CashBalance)
        .where(CashBalance.is_latest == True)  # noqa: E712
        .order_by(CashBalance.account_id, CashBalance.currency)
    )
    if account_id is not None:
        statement = statement.where(CashBalance.account_id == account_id)
    return list(session.scalars(statement))


# ═══════════════════════════════════════════════════════════════════════
# Transactions
# ═══════════════════════════════════════════════════════════════════════


def create_transaction(session: Session, **kwargs) -> Transaction:
    txn = Transaction(id=uuid4(), **kwargs)
    session.add(txn)
    session.flush()
    return txn


def list_transactions(
    session: Session,
    account_id: Optional[UUID] = None,
    asset_id: Optional[UUID] = None,
    *,
    limit: int = 100,
) -> list[Transaction]:
    statement = (
        select(Transaction)
        .order_by(Transaction.executed_at.desc())
        .limit(limit)
    )
    if account_id is not None:
        statement = statement.where(Transaction.account_id == account_id)
    if asset_id is not None:
        statement = statement.where(Transaction.asset_id == asset_id)
    return list(session.scalars(statement))


# ═══════════════════════════════════════════════════════════════════════
# FX Rates
# ═══════════════════════════════════════════════════════════════════════


def create_fx_rate(session: Session, **kwargs) -> FxRate:
    rate = FxRate(id=uuid4(), **kwargs)
    session.add(rate)
    session.flush()
    return rate


def get_latest_fx_rate(
    session: Session, from_currency: str, to_currency: str, *, before: Optional[datetime] = None,
) -> Optional[FxRate]:
    statement = (
        select(FxRate)
        .where(
            FxRate.from_currency == from_currency,
            FxRate.to_currency == to_currency,
        )
        .order_by(FxRate.observed_at.desc())
        .limit(1)
    )
    if before is not None:
        statement = statement.where(FxRate.observed_at <= before)
    return session.scalar(statement)


# ═══════════════════════════════════════════════════════════════════════
# Data Sources
# ═══════════════════════════════════════════════════════════════════════


def get_data_source_by_key(session: Session, source_key: str) -> Optional[DataSource]:
    return session.scalar(
        select(DataSource).where(DataSource.source_key == source_key)
    )


def create_data_source(session: Session, **kwargs) -> DataSource:
    source = DataSource(id=uuid4(), **kwargs)
    session.add(source)
    session.flush()
    return source


def list_active_data_sources(session: Session) -> list[DataSource]:
    return list(
        session.scalars(
            select(DataSource)
            .where(DataSource.is_active == True)  # noqa: E712
            .order_by(DataSource.source_key.asc())
        )
    )
