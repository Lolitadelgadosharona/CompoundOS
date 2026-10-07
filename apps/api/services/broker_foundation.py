"""Offline read-only normalization/staging foundation; no network, ledger writes or orders.

The store is an isolated reference implementation, NOT durable application storage.
A future repository must provide the same atomic/tenant-scoped contract.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from apps.api.services.instrument_resolver import (
    Instrument,
    InstrumentUnavailable,
    canonical_asset,
    identity_dimensions,
)


class BrokerCapability(str, Enum):
    ACCOUNT_READ = "ACCOUNT_READ"
    POSITIONS_READ = "POSITIONS_READ"
    CASH_READ = "CASH_READ"
    TRANSACTIONS_READ = "TRANSACTIONS_READ"
    COST_BASIS_READ = "COST_BASIS_READ"
    ORDER_PREVIEW = "ORDER_PREVIEW"
    ORDER_EXECUTE = "ORDER_EXECUTE"
    TRANSFER = "TRANSFER"
    WITHDRAWAL = "WITHDRAWAL"


READ_CAPABILITIES = frozenset(c for c in BrokerCapability if c.value.endswith("_READ"))


@dataclass(frozen=True)
class BrokerConnection:
    owner_id: UUID
    connection_id: UUID
    provider: str
    capabilities: frozenset[BrokerCapability]

    def __post_init__(self):
        if (
            not self.provider
            or not all(isinstance(c, BrokerCapability) for c in self.capabilities)
            or not self.capabilities <= READ_CAPABILITIES
        ):
            raise ValueError("Only enumerated read capabilities are supported")


@dataclass(frozen=True)
class Provenance:
    provider: str
    reference: str
    as_of: datetime
    retrieved_at: datetime
    quality: str
    source: str = "BROKER"

    def __post_init__(self):
        if not self.provider or not self.reference:
            raise ValueError("Missing provenance")
        if self.source not in {"MANUAL", "BROKER", "DEMO"}:
            raise ValueError("Invalid source")
        if self.quality not in {"LIVE", "DELAYED", "STALE", "UNKNOWN"}:
            raise ValueError("Invalid quality")
        if not self.as_of.tzinfo or not self.retrieved_at.tzinfo:
            raise ValueError("Timezone required")
        if self.as_of > self.retrieved_at:
            raise ValueError("Future observation")


@dataclass(frozen=True)
class BrokerAccount:
    external_id: str
    currency: str
    provenance: Provenance


@dataclass(frozen=True)
class BrokerPosition:
    external_id: str
    account_ref: str
    quantity: Decimal
    currency: str
    provenance: Provenance
    instrument: Instrument | None
    cost_basis: Decimal | None = None
    canonical_id: UUID | None = None
    status: str = "UNRESOLVED"


@dataclass(frozen=True)
class BrokerCashBalance:
    external_id: str
    account_ref: str
    amount: Decimal
    currency: str
    provenance: Provenance


@dataclass(frozen=True)
class BrokerTransaction:
    external_id: str
    account_ref: str
    amount: Decimal
    currency: str
    provenance: Provenance
    kind: str


@dataclass(frozen=True)
class BrokerSnapshot:
    accounts: tuple[BrokerAccount, ...]
    positions: tuple[BrokerPosition, ...]
    cash: tuple[BrokerCashBalance, ...]
    transactions: tuple[BrokerTransaction, ...]
    complete: bool


class BrokerProvider(Protocol):
    """Read methods only; no executable trading interface."""

    capabilities: frozenset[BrokerCapability]

    def read_snapshot(self) -> BrokerSnapshot: ...


class CanonicalResolver:
    def __init__(self, session):
        self.session = session

    def __call__(self, instrument):
        identity_dimensions(instrument)
        return canonical_asset(self.session, instrument).id


def normalize_position(position, resolver):
    # Ticker alone is never upgraded to a trusted UUID.
    if not position.instrument:
        return replace(position, canonical_id=None, status="UNRESOLVED")
    try:
        identity_dimensions(position.instrument)
        if position.currency != position.instrument.currency:
            raise InstrumentUnavailable("Currency mismatch")
        asset_id = resolver(position.instrument)
        if not isinstance(asset_id, UUID):
            raise InstrumentUnavailable("Canonical UUID required")
        return replace(position, canonical_id=asset_id, status="CURRENT")
    except InstrumentUnavailable:
        return replace(position, canonical_id=None, status="UNRESOLVED")


@dataclass(frozen=True)
class BrokerSyncRun:
    connection_id: UUID
    provider: str
    started_at: datetime
    completed_at: datetime
    status: str
    received: int
    accepted: int
    rejected: int
    unresolved: int
    error_code: str | None


class StagingStore:
    """No production wiring. Failure never replaces last successful snapshot.

    Transactions merge by external ID; complete holdings replace atomically.
    No strategy, policy, price, FX or approval dependency exists here.
    """

    def __init__(self):
        self.snapshots = {}
        self.runs = []
        self.last_success = {}
        self.latest_run = {}

    def sync(self, connection, snapshot, resolver, now):
        key = (connection.owner_id, connection.connection_id)
        rows = (*snapshot.accounts, *snapshot.positions, *snapshot.cash, *snapshot.transactions)
        try:
            if not snapshot.complete:
                raise ValueError("Incomplete snapshot")
            required = {
                BrokerCapability.ACCOUNT_READ,
                BrokerCapability.POSITIONS_READ,
                BrokerCapability.CASH_READ,
                BrokerCapability.TRANSACTIONS_READ,
            }
            if not required <= connection.capabilities:
                raise ValueError("Missing read permission")
            accounts = {a.external_id for a in snapshot.accounts}
            for collection in (
                snapshot.accounts,
                snapshot.positions,
                snapshot.cash,
                snapshot.transactions,
            ):
                ids = [r.external_id for r in collection]
                if len(ids) != len(set(ids)):
                    raise ValueError("Duplicate identity")
                for row in collection:
                    if (
                        not row.external_id
                        or len(row.currency) != 3
                        or not row.currency.isupper()
                        or not row.currency.isalpha()
                    ):
                        raise ValueError("Invalid identity/currency")
                    if (
                        row.provenance.provider != connection.provider
                        or row.provenance.retrieved_at > now
                    ):
                        raise ValueError("Invalid provenance")
                    if hasattr(row, "account_ref") and row.account_ref not in accounts:
                        raise ValueError("Unknown account")
                    for field in ("quantity", "amount", "cost_basis"):
                        amount = getattr(row, field, None)
                        if amount is not None and (
                            not isinstance(amount, Decimal) or not amount.is_finite()
                        ):
                            raise ValueError("Invalid amount")
                    if isinstance(row, BrokerPosition) and row.quantity < 0:
                        raise ValueError("Short positions require separate design")
            previous_snapshot = self.snapshots.get(key)
            if previous_snapshot:
                old_by_id = {
                    (type(r), r.external_id): r
                    for r in (
                        *previous_snapshot.accounts,
                        *previous_snapshot.positions,
                        *previous_snapshot.cash,
                    )
                }
                for row in (*snapshot.accounts, *snapshot.positions, *snapshot.cash):
                    old = old_by_id.get((type(row), row.external_id))
                    if old and row.provenance.as_of < old.provenance.as_of:
                        raise ValueError("Out-of-order observation")
            positions = tuple(normalize_position(p, resolver) for p in snapshot.positions)
            previous = self.snapshots.get(key)
            transactions = {t.external_id: t for t in previous.transactions} if previous else {}
            for transaction in snapshot.transactions:
                if (
                    transaction.external_id in transactions
                    and transactions[transaction.external_id] != transaction
                ):
                    raise ValueError("Conflicting transaction identity")
                transactions[transaction.external_id] = transaction
            staged = replace(
                snapshot, positions=positions, transactions=tuple(transactions.values())
            )
            unresolved = sum(p.status == "UNRESOLVED" for p in positions)
            self.snapshots[key] = staged
            self.last_success[key] = now
            run = BrokerSyncRun(
                connection.connection_id,
                connection.provider,
                now,
                now,
                "UNRESOLVED" if unresolved else "CURRENT",
                len(rows),
                len(rows) - unresolved,
                0,
                unresolved,
                None,
            )
        except Exception:
            # Provider/resolver failures are sanitized; previous snapshot is retained.
            # No raw provider error/payload in diagnostics.
            run = BrokerSyncRun(
                connection.connection_id,
                connection.provider,
                now,
                now,
                "SYNC_FAILED",
                len(rows),
                0,
                len(rows),
                0,
                "SNAPSHOT_REJECTED",
            )
        self.runs.append(run)
        self.latest_run[(connection.owner_id, connection.connection_id)] = run
        return run

    def fail(self, connection, now):
        run = BrokerSyncRun(
            connection.connection_id,
            connection.provider,
            now,
            now,
            "SYNC_FAILED",
            0,
            0,
            0,
            0,
            "PROVIDER_UNAVAILABLE",
        )
        self.runs.append(run)
        self.latest_run[(connection.owner_id, connection.connection_id)] = run
        return run

    def view(self, connection, now, max_age=timedelta(hours=24)):
        key = (connection.owner_id, connection.connection_id)
        snapshot = self.snapshots.get(key)
        latest_run = self.latest_run.get(key)
        if not snapshot:
            return {"snapshot": None, "status": "UNKNOWN", "recommendation_ready": False}
        observations = (*snapshot.accounts, *snapshot.positions, *snapshot.cash)
        stale = any(
            now - r.provenance.as_of > max_age
            or r.provenance.as_of > now
            or r.provenance.quality in {"STALE", "UNKNOWN"}
            or r.provenance.source == "DEMO"
            for r in observations
        )
        status = (
            "SYNC_FAILED"
            if latest_run.status == "SYNC_FAILED"
            else (
                "UNRESOLVED"
                if any(p.status == "UNRESOLVED" for p in snapshot.positions)
                else "STALE"
                if stale
                else "CURRENT"
            )
        )
        return {
            "snapshot": snapshot,
            "status": status,
            "last_success": self.last_success[key],
            # Broker freshness alone NEVER establishes investment readiness.
            "recommendation_ready": False,
        }


def aggregate_native(snapshots):
    """Read-only inventory by currency/UUID; never sums money across currencies."""
    cash, quantities = {}, {}
    for snapshot in snapshots:
        for row in snapshot.cash:
            cash[row.currency] = cash.get(row.currency, Decimal(0)) + row.amount
        for row in snapshot.positions:
            if row.canonical_id:
                quantities[row.canonical_id] = (
                    quantities.get(row.canonical_id, Decimal(0)) + row.quantity
                )
    return {
        "cash_by_currency": cash,
        "quantity_by_instrument": quantities,
        "recommendation_ready": False,
    }


@dataclass(frozen=True)
class ManualProvider:
    """Offline adapter for explicitly supplied manual records; no credentials/network."""

    snapshot: BrokerSnapshot
    capabilities: frozenset[BrokerCapability] = READ_CAPABILITIES

    def __post_init__(self):
        if (
            not all(isinstance(c, BrokerCapability) for c in self.capabilities)
            or not self.capabilities <= READ_CAPABILITIES
        ):
            raise ValueError("Read capabilities only")
        rows = (
            *self.snapshot.accounts,
            *self.snapshot.positions,
            *self.snapshot.cash,
            *self.snapshot.transactions,
        )
        if any(row.provenance.source != "MANUAL" for row in rows):
            raise ValueError("Manual adapter requires explicit manual provenance")

    def read_snapshot(self):
        return self.snapshot
