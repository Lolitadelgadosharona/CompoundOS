"""Provider-agnostic connector interfaces (Protocol classes only, no implementations).

Sprint 009 Slice D — design only. No broker connections.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass
class AssetIdentifier:
    isin: str | None = None
    symbol: str | None = None
    exchange: str | None = None
    currency: str | None = None


@dataclass
class AccountImportResult:
    provider_account_id: str
    account_name: str
    account_type: str
    currency: str
    raw_data: dict  # provider-specific, for debugging


@dataclass
class PositionImportResult:
    provider_record_id: str
    asset_identifier: AssetIdentifier
    quantity: Decimal
    avg_cost: Decimal | None
    market_price: Decimal | None
    observed_at: datetime
    raw_data: dict


@dataclass
class TransactionImportResult:
    provider_record_id: str
    asset_identifier: AssetIdentifier | None
    transaction_type: str
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal | None
    fee: Decimal | None
    executed_at: datetime
    raw_data: dict


@dataclass
class BalanceImportResult:
    provider_record_id: str
    currency: str
    amount: Decimal
    observed_at: datetime
    raw_data: dict


class AccountImporter(Protocol):
    """Import account metadata from a provider."""

    def import_accounts(self, household_id: UUID) -> list[AccountImportResult]: ...


class PositionImporter(Protocol):
    """Import current positions from a provider."""

    def import_positions(self, account_id: UUID) -> list[PositionImportResult]: ...


class TransactionImporter(Protocol):
    """Import transaction history from a provider."""

    def import_transactions(
        self, account_id: UUID, from_date: date, to_date: date,
    ) -> list[TransactionImportResult]: ...


class BalanceImporter(Protocol):
    """Import cash balances from a provider."""

    def import_balances(self, account_id: UUID) -> list[BalanceImportResult]: ...
