"""Synthetic staging only; no live broker, no ledger/database writes."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from uuid import uuid4

import pytest

from apps.api.services.broker_foundation import (
    READ_CAPABILITIES,
    BrokerAccount,
    BrokerCapability,
    BrokerCashBalance,
    BrokerConnection,
    BrokerPosition,
    BrokerSnapshot,
    BrokerTransaction,
    Provenance,
    StagingStore,
    aggregate_native,
)
from apps.api.services.instrument_resolver import Instrument

NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def fixture():
    p = Provenance("synthetic", "record", NOW, NOW, "DELAYED")
    c = BrokerConnection(uuid4(), uuid4(), "synthetic", READ_CAPABILITIES)
    i = Instrument("BRK.B", "Berkshire B", "NYSE", "STOCK", "USD", "synthetic", "BRK.B")
    s = BrokerSnapshot(
        (BrokerAccount("a", "USD", p), BrokerAccount("b", "CNY", p)),
        (BrokerPosition("p", "a", D("2.5"), "USD", p, i),),
        (
            BrokerCashBalance("c", "a", D("10"), "USD", p),
            BrokerCashBalance("d", "b", D("100"), "CNY", p),
        ),
        (BrokerTransaction("t", "a", D("10"), "USD", p, "CONTRIBUTION"),),
        True,
    )
    return c, s


@pytest.mark.parametrize("cap", [c for c in BrokerCapability if c not in READ_CAPABILITIES])
def test_no_execution_capability(cap):
    with pytest.raises(ValueError):
        BrokerConnection(uuid4(), uuid4(), "synthetic", frozenset({cap}))


def test_normalization_idempotency_multiple_accounts_provenance_and_strategy_separation():
    c, s = fixture()
    store = StagingStore()
    asset = uuid4()
    strategy = {"another_asset": "100"}
    seen = []

    def resolver(identity):
        seen.append(identity)
        return asset

    for _ in range(2):
        assert store.sync(c, s, resolver, NOW).status == "CURRENT"
    view = store.view(c, NOW)
    normalized = view["snapshot"]
    assert len(normalized.accounts) == 2 and len(normalized.transactions) == 1
    assert seen[0].symbol == "BRK.B" and normalized.positions[0].canonical_id == asset
    assert normalized.positions[0].provenance == s.positions[0].provenance
    assert normalized.positions[0].quantity == D("2.5")
    assert strategy == {"another_asset": "100"}
    assert not view["recommendation_ready"]
    manual = replace(
        normalized,
        positions=(),
        transactions=(),
        cash=(replace(s.cash[0], provenance=replace(s.cash[0].provenance, source="MANUAL")),),
    )
    totals = aggregate_native([normalized, manual])
    assert totals["cash_by_currency"] == {"USD": D("20"), "CNY": D("100")}
    assert totals["quantity_by_instrument"] == {asset: D("2.5")}


@pytest.mark.parametrize(
    "instrument", [None, Instrument("BRK.B", "B", "", "STOCK", "USD", "s", "B")]
)
def test_unresolved_never_trusted(instrument):
    c, s = fixture()
    s = replace(s, positions=(replace(s.positions[0], instrument=instrument),))
    store = StagingStore()
    assert store.sync(c, s, lambda i: uuid4(), NOW).unresolved == 1
    assert store.view(c, NOW)["status"] == "UNRESOLVED"
    assert store.view(c, NOW)["snapshot"].positions[0].canonical_id is None


def test_failure_stale_and_conflicting_transaction_preserve_previous():
    c, s = fixture()
    store = StagingStore()
    store.sync(c, s, lambda i: uuid4(), NOW)
    previous = store.view(c, NOW)["snapshot"]
    assert store.view(c, NOW + timedelta(days=2))["status"] == "STALE"
    store.fail(c, NOW)
    assert store.view(c, NOW)["status"] == "SYNC_FAILED"
    assert store.view(c, NOW)["snapshot"] is previous
    conflict = replace(s, transactions=(replace(s.transactions[0], amount=D("11")),))
    assert store.sync(c, conflict, lambda i: uuid4(), NOW).status == "SYNC_FAILED"
    assert store.view(c, NOW)["snapshot"] is previous


@pytest.mark.parametrize(
    "mode", ["incomplete", "duplicate", "nonfinite", "currency", "account", "short"]
)
def test_invalid_batch_rejected_atomically(mode):
    c, s = fixture()
    if mode == "incomplete":
        s = replace(s, complete=False)
    elif mode == "duplicate":
        s = replace(s, transactions=s.transactions * 2)
    elif mode == "nonfinite":
        s = replace(s, cash=(replace(s.cash[0], amount=D("NaN")),))
    elif mode == "currency":
        s = replace(s, cash=(replace(s.cash[0], currency="GBp"),))
    elif mode == "account":
        s = replace(s, cash=(replace(s.cash[0], account_ref="unknown"),))
    else:
        s = replace(s, positions=(replace(s.positions[0], quantity=D("-1")),))
    store = StagingStore()
    assert store.sync(c, s, lambda i: uuid4(), NOW).status == "SYNC_FAILED"
    assert store.view(c, NOW)["snapshot"] is None


def test_provenance_future_and_naive_rejected():
    with pytest.raises(ValueError):
        Provenance("x", "r", NOW + timedelta(seconds=1), NOW, "LIVE")
    with pytest.raises(ValueError):
        Provenance("x", "r", NOW.replace(tzinfo=None), NOW, "LIVE")


def test_foundation_has_no_execution_or_approval_path():
    from apps.api.services.broker_foundation import BrokerProvider

    assert not any(
        hasattr(BrokerProvider, name) for name in ("execute", "order", "transfer", "withdraw")
    )
    import inspect

    from apps.api.services import launch_investment

    assert "broker_foundation" not in inspect.getsource(launch_investment.approve)


def test_unexpected_resolver_failure_and_old_data_preserve_state():
    c, s = fixture()
    store = StagingStore()
    store.sync(c, s, lambda i: uuid4(), NOW)
    prior = store.view(c, NOW)["snapshot"]

    def unavailable(i):
        raise RuntimeError("private provider response must not be logged")

    assert store.sync(c, s, unavailable, NOW).error_code == "SNAPSHOT_REJECTED"
    assert store.view(c, NOW)["snapshot"] is prior
    old = replace(
        s,
        positions=(
            replace(
                s.positions[0],
                provenance=replace(s.positions[0].provenance, as_of=NOW - timedelta(days=1)),
            ),
        ),
    )
    assert store.sync(c, old, lambda i: uuid4(), NOW).status == "SYNC_FAILED"
    assert store.view(c, NOW)["snapshot"] is prior


def test_manual_adapter_and_owner_isolation():
    from apps.api.services.broker_foundation import ManualProvider

    c, s = fixture()
    with pytest.raises(ValueError):
        ManualProvider(s)
    manual = replace(
        s,
        accounts=tuple(
            replace(a, provenance=replace(a.provenance, source="MANUAL")) for a in s.accounts
        ),
        positions=(),
        cash=(),
        transactions=(),
    )
    assert ManualProvider(manual).read_snapshot() == manual
    store = StagingStore()
    store.sync(c, s, lambda i: uuid4(), NOW)
    other_owner = replace(c, owner_id=uuid4())
    store.fail(other_owner, NOW)
    assert store.view(c, NOW)["status"] == "CURRENT"
    assert store.view(other_owner, NOW)["status"] == "UNKNOWN"
