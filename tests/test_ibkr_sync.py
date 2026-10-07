# ruff: noqa: F811
"""Durable sync/ledger/approval/read-only regressions in fresh isolated PostgreSQL."""

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from apps.api.services import ibkr_sync
from apps.api.services import launch_investment as svc
from apps.api.services.valuation import RecommendationUnavailable, load_valuation
from tests.test_ibkr_adapter import provider as ibkr_provider
from tests.test_ibkr_adapter import responses
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup
from tests.test_owner_preview import preview


@pytest.mark.postgres
def test_full_import_repeated_sync_preserves_strategy_and_no_quotes_or_transactions(
    db_session, setup
):
    hid, _, _, _ = setup
    original = svc.configuration(db_session, hid)
    cfg = json.dumps(original["settings"], sort_keys=True, default=str)
    market = db_session.execute(text("SELECT count(*) FROM market_observations")).scalar()
    for _ in range(2):
        result = ibkr_sync.sync(db_session, hid, ibkr_provider())
        assert result["status"] == "CONNECTED" and result["connection_type"] == "PAPER"
        assert result["positions"] == 4 and result["unresolved"] == 0
        assert result["holdings"][-1]["symbol"] == "BRK.B"
        assert result["holdings"][0]["target"] == "0" and result["holdings"][0]["non_target"]
    assert (
        json.dumps(svc.configuration(db_session, hid)["settings"], sort_keys=True, default=str)
        == cfg
    )
    assert svc.configuration(db_session, hid)["id"] == original["id"]
    assert (
        db_session.execute(
            text("SELECT count(*) FROM positions WHERE source='interactive_brokers' AND is_latest")
        ).scalar()
        == 4
    )
    assert (
        db_session.execute(
            text(
                "SELECT count(*) FROM cash_balances "
                "WHERE source='interactive_brokers' AND is_latest"
            )
        ).scalar()
        == 2
    )
    assert db_session.execute(text("SELECT count(*) FROM transactions")).scalar() == 0
    assert db_session.execute(text("SELECT count(*) FROM market_observations")).scalar() == market
    v = load_valuation(db_session, hid)
    assert not v.recommendation_ready and "NOT LIVE" in ";".join(v.reasons)
    assert v.contract()["data_mode"] == "MIXED"
    assert v.total() is None
    with pytest.raises(RecommendationUnavailable):
        svc.make_candidate(db_session, hid)
    snapshot = db_session.execute(
        text("SELECT snapshot FROM ibkr_read_sync_runs ORDER BY completed_at DESC LIMIT 1")
    ).scalar()
    assert "NEVER_PERSIST_THIS" not in json.dumps(snapshot)
    assert "conid" in json.dumps(snapshot) and "as_of_basis" in json.dumps(snapshot)


@pytest.mark.postgres
def test_failure_disconnect_stale_preserve_previous_positions(db_session, setup):
    hid, *_ = setup
    result = ibkr_sync.sync(db_session, hid, ibkr_provider())
    stamp = result["last_sync"]
    ids = list(
        db_session.execute(
            text("SELECT id FROM positions WHERE source='interactive_brokers' AND is_latest")
        ).scalars()
    )
    v = responses()
    v["/portfolio/accounts"] = None
    failed = ibkr_sync.sync(db_session, hid, ibkr_provider(v))
    assert (
        failed["status"] == "SYNC_FAILED"
        and failed["positions"] == 4
        and failed["last_sync"] == stamp
    )
    assert (
        list(
            db_session.execute(
                text("SELECT id FROM positions WHERE source='interactive_brokers' AND is_latest")
            ).scalars()
        )
        == ids
    )
    result = ibkr_sync.disconnect(db_session, hid)
    assert result["status"] == "DISCONNECTED"
    assert not load_valuation(db_session, hid).recommendation_ready
    result = ibkr_sync.sync(db_session, hid, ibkr_provider())
    assert result["status"] == "CONNECTED"


@pytest.mark.postgres
def test_unresolved_batch_keeps_last_known_ledger_and_blocks(db_session, setup):
    hid, *_ = setup
    ibkr_sync.sync(db_session, hid, ibkr_provider())
    v = responses()
    v["/trsrv/secdef?conids=4"]["secdef"][0]["listingExchange"] = None
    result = ibkr_sync.sync(db_session, hid, ibkr_provider(v))
    assert result["unresolved"] == 1 and result["holdings"][-1]["identity_status"] == "UNRESOLVED"
    assert result["holdings"][-1]["canonical_id"] is None
    assert (
        db_session.execute(
            text("SELECT count(*) FROM positions WHERE source='interactive_brokers' AND is_latest")
        ).scalar()
        == 4
    )
    assert not load_valuation(db_session, hid).recommendation_ready


@pytest.mark.postgres
def test_stale_cash_and_multiple_accounts(db_session, setup):
    from datetime import datetime, timezone

    hid, *_ = setup
    v = responses()
    other = responses("DU7654321", "DEMO")
    v["/portfolio/accounts"] += other.pop("/portfolio/accounts")
    v.update({k: val for k, val in other.items() if k.startswith("/portfolio/")})
    old = int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())
    v["/portfolio/DU1234567/ledger"]["USD"]["timestamp"] = old
    result = ibkr_sync.sync(db_session, hid, ibkr_provider(v))
    assert (
        result["accounts_discovered"] == 2
        and result["positions"] == 8
        and result["status"] == "STALE"
    )
    assert (
        db_session.execute(
            text(
                "SELECT count(DISTINCT asset_id) FROM positions "
                "WHERE source='interactive_brokers' AND is_latest"
            )
        ).scalar()
        == 4
    )


@pytest.mark.postgres
def test_api_origin_capability_and_auth_artifact_boundary(
    db_session, setup, api_client, monkeypatch
):
    hid, *_ = setup
    test_url = db_session.bind.url.render_as_string(hide_password=False)
    preview(monkeypatch)
    monkeypatch.setattr("apps.api.mutation_gate.get_database_url", lambda: test_url)
    monkeypatch.delenv("COMPOUNDOS_IBKR_READ_ENABLED", raising=False)
    assert api_client.post("/api/investment/ibkr/sync", json={}).status_code == 403
    headers = {"Origin": "http://localhost:3802"}
    response = api_client.post("/api/investment/ibkr/sync", json={}, headers=headers)
    assert response.status_code == 409 and "OWNER_SETUP_REQUIRED" in response.text
    monkeypatch.setattr(ibkr_sync, "configured_provider", lambda: ibkr_provider())
    response = api_client.post(
        "/api/investment/ibkr/sync", json={"password": "never-store"}, headers=headers
    )
    assert response.status_code == 422 and "never-store" not in response.text
    response = api_client.post("/api/investment/ibkr/sync", json={}, headers=headers)
    assert response.status_code == 200
    assert "DU1234567" not in response.text and "NEVER_PERSIST_THIS" not in response.text
    assert "cookie" not in response.text and "password" not in response.text
    for endpoint in ("/api/broker/orders", "/api/transactions", "/api/investment/ibkr/order"):
        assert api_client.post(endpoint, json={}, headers=headers).status_code in (403, 404)
    overview = api_client.get("/api/investment/owner-overview").json()
    assert overview["snapshot"]["valuation"]["data_mode"] == "MIXED"
    assert overview["analysis"] is None
    assert overview["connections"]["brokers"][0]["connection_type"] == "PAPER"


@pytest.mark.postgres
def test_append_only_sync_history_and_populated_downgrade_refuses(db_session, setup):
    hid, *_ = setup
    ibkr_sync.sync(db_session, hid, ibkr_provider())
    with pytest.raises(Exception):
        db_session.execute(text("UPDATE ibkr_read_sync_runs SET received=0"))
        db_session.commit()
    db_session.rollback()
    from importlib import import_module

    migration = import_module("migrations.versions.0037_ibkr_read_only")
    from unittest.mock import patch

    with (
        patch.object(migration.op, "get_bind", return_value=db_session),
        pytest.raises(RuntimeError, match="history present"),
    ):
        migration.downgrade()


@pytest.mark.postgres
def test_older_snapshot_rejected_without_ledger_change(db_session, setup):
    hid, *_ = setup
    ibkr_sync.sync(db_session, hid, ibkr_provider())
    before = (
        db_session.execute(
            text("SELECT id FROM positions WHERE source='interactive_brokers' AND is_latest")
        )
        .scalars()
        .all()
    )
    v = responses()
    v["/portfolio/DU1234567/ledger"]["USD"]["timestamp"] -= 100
    result = ibkr_sync.sync(db_session, hid, ibkr_provider(v))
    assert (
        result["status"] == "SYNC_FAILED" and result["error_code"] == "IBKR_OUT_OF_ORDER_SNAPSHOT"
    )
    assert (
        db_session.execute(
            text("SELECT id FROM positions WHERE source='interactive_brokers' AND is_latest")
        )
        .scalars()
        .all()
        == before
    )


@pytest.mark.postgres
def test_actual_approval_has_no_ibkr_read_or_execution_call(db_session, setup, monkeypatch):
    from apps.api.services.ibkr_adapter import GatewayReader, InteractiveBrokersProvider

    def forbidden(*args, **kwargs):
        pytest.fail("Investment approval crossed broker adapter boundary")

    monkeypatch.setattr(GatewayReader, "get", forbidden)
    monkeypatch.setattr(InteractiveBrokersProvider, "read_result", forbidden)
    from tests.test_launch_v1 import test_approval_journal_audit_manual_only

    test_approval_journal_audit_manual_only(db_session, setup)


@pytest.mark.postgres
def test_empty_ibkr_migration_downgrade_upgrade(postgres_test_isolation, postgres_engine):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    cfg.attributes["connection"] = postgres_engine
    command.downgrade(cfg, "0036_launch_hardening")
    assert "ibkr_read_sync_runs" not in inspect(postgres_engine).get_table_names()
    command.upgrade(cfg, "head")
    assert "ibkr_read_sync_runs" in inspect(postgres_engine).get_table_names()
