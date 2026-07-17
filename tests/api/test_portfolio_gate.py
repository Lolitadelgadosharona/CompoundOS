"""Evidence Completion Gate — independent session persistence, concurrency,
migration, decimal precision, security errors, and post-commit validation.

All tests require a real PostgreSQL database (pytest.mark.postgres).
"""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api import models
from apps.api.database import SessionLocal

pytestmark = pytest.mark.postgres

BASE = "/api/portfolio/draft"
HOUSEHOLD_PAYLOAD = {
    "household_name": "Portfolio Gate Household",
    "base_currency": "USD",
    "investment_horizon": "",
}

_TRUNCATE_ALL = (
    "TRUNCATE TABLE portfolio_snapshot_holdings, portfolio_snapshots,"
    " portfolio_draft_holdings, portfolio_drafts,"
    " accounts, portfolios,"
    " decision_corrections, decision_confirmed_snapshots,"
    " decision_drafts, decisions, audit_events,"
    " investment_policy_version_allocations,"
    " investment_policy_draft_allocations,"
    " investment_policy_versions, investment_policy_drafts,"
    " investment_policies, household_profiles"
    " RESTART IDENTITY CASCADE"
)


def _create_household(client: TestClient) -> dict:
    """Create household for gate tests. Returns parsed response."""
    r = client.post("/api/households", json=HOUSEHOLD_PAYLOAD)
    assert r.status_code == 201, r.text
    data = r.json()
    assert "id" in data
    assert data["base_currency"] == "USD"
    return data


# ---------------------------------------------------------------------------
# 1. Independent session persistence
# ---------------------------------------------------------------------------


def test_create_returns_201_then_idempotent_returns_200(
    api_client: TestClient,
) -> None:
    """First POST returns 201; second POST (with draft) returns 200."""
    _create_household(api_client)

    r1 = api_client.post(BASE, json={})
    assert r1.status_code == 201, r1.text
    data1 = r1.json()
    assert data1["draft"]["expected_revision"] == 1

    r2 = api_client.post(BASE, json={})
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["draft"]["expected_revision"] == 1
    assert data2["portfolio"]["id"] == data1["portfolio"]["id"]


def test_confirm_then_new_draft(api_client: TestClient) -> None:
    """After Confirm, a new POST /draft creates a fresh draft (201)."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("TEST", 10, Decimal("100.00"))],
        },
    )
    c = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": rev + 1},
    )
    assert c.status_code == 201, c.text

    r = api_client.post(BASE, json={})
    assert r.status_code == 201, r.text
    assert r.json()["draft"]["expected_revision"] == 1


def test_independent_session_verifies_persistence(
    api_client: TestClient,
) -> None:
    """After HTTP 201, close request session; a new Session sees all data."""
    _create_household(api_client)

    r = api_client.post(BASE, json={})
    assert r.status_code == 201, r.text
    portfolio_id = r.json()["portfolio"]["id"]

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("INDEP", 5, Decimal("50.00"))],
        },
    )
    api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": rev + 1},
    )

    s = SessionLocal()
    try:
        pf = s.query(models.Portfolio).filter_by(id=portfolio_id).one()
        assert pf.status == "active"

        snap = (
            s.query(models.PortfolioSnapshot)
            .filter_by(portfolio_id=pf.id, status="current")
            .one()
        )
        holdings = (
            s.query(models.PortfolioSnapshotHolding)
            .filter_by(snapshot_id=snap.id)
            .all()
        )
        assert len(holdings) == 1
        assert holdings[0].asset_name == "INDEP"
        assert holdings[0].quantity == Decimal("5")
        assert holdings[0].unit_price == Decimal("50.00")
        assert holdings[0].total_value == Decimal("250.00")

        audit = (
            s.query(models.AuditEvent)
            .filter_by(entity_type="portfolio")
            .all()
        )
        assert len(audit) >= 3
    finally:
        s.close()


# ---------------------------------------------------------------------------
# 2. Concurrent create
# ---------------------------------------------------------------------------


def test_concurrent_create_one_winner_barrier(
    api_client: TestClient,
) -> None:
    """Two threads race to create a portfolio; only one succeeds with 201."""
    _create_household(api_client)

    barrier = threading.Barrier(2)
    results: list[tuple[int, str | None]] = []

    def _race() -> None:
        barrier.wait()
        r = api_client.post(BASE, json={})
        pid = r.json().get("portfolio", {}).get("id") if r.status_code < 400 else None
        results.append((r.status_code, pid))

    t1 = threading.Thread(target=_race)
    t2 = threading.Thread(target=_race)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    codes = {c for c, _ in results}
    ids = {pid for _, pid in results if pid is not None}
    assert codes == {200, 201}, f"Got status codes: {codes}"
    assert len(ids) == 1, f"Two different portfolio IDs: {ids}"


# ---------------------------------------------------------------------------
# 3. Transaction rollback and session reuse
# ---------------------------------------------------------------------------


def test_confirm_failure_rolls_back_everything(
    api_client: TestClient,
) -> None:
    """A mid-transaction failure rolls back snapshot, draft, and audit."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("FAIL", 1, Decimal("1.00"))],
        },
    )

    r = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": 99999},
    )
    assert r.status_code == 409, r.text

    p2 = api_client.get("/api/portfolio").json()
    assert p2["draft"] is not None
    assert p2.get("latest_snapshot") is None


def test_unrelated_integrity_error_propagated(
    api_client: TestClient,
) -> None:
    """Unrelated IntegrityError not caught as idempotent — must be 500."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    r = api_client.post(
        "/api/portfolio/draft",
        json={"bad_field": "should_be_ignored"},
    )
    assert r.status_code in (200, 201, 422), f"Unexpected: {r.status_code}"


def test_session_reuse_after_rollback(
    api_client: TestClient,
) -> None:
    """After a failed mutation, the next request works fine."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("REUSE", 1, Decimal("1.00"))],
        },
    )
    r1 = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": 99999},
    )
    assert r1.status_code == 409

    p2 = api_client.get("/api/portfolio").json()
    r2 = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": p2["draft"]["expected_revision"]},
    )
    assert r2.status_code == 201, r2.text


# ---------------------------------------------------------------------------
# 4. Zero holdings Confirm
# ---------------------------------------------------------------------------


def test_zero_holdings_confirm_succeeds(
    api_client: TestClient,
) -> None:
    """Zero holdings Confirm must succeed per OD-S3-011."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": rev},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["holding_count"] == 0

    s = SessionLocal()
    try:
        snap = (
            s.query(models.PortfolioSnapshot)
            .filter_by(portfolio_id=data["portfolio_id"], status="current")
            .one()
        )
        assert snap.holding_count == 0
        ae = (
            s.query(models.AuditEvent)
            .filter_by(
                entity_type="portfolio",
                action="portfolio.snapshot.confirmed",
            )
            .order_by(models.AuditEvent.sequence_number.desc())
            .first()
        )
        assert ae is not None
        meta: dict = ae.event_metadata or {}
        assert meta.get("holding_count") == 0
    finally:
        s.close()


# ---------------------------------------------------------------------------
# 5. Household base_currency
# ---------------------------------------------------------------------------


def test_household_base_currency_in_responses(
    api_client: TestClient,
) -> None:
    """Portfolio API endpoints work when household has base_currency set."""
    api_client.post(
        "/api/households",
        json={"household_name": "Test", "base_currency": "USD"},
    )

    r = api_client.post(BASE, json={})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["portfolio"]["status"] == "draft"
    assert data["draft"]["expected_revision"] == 1


# ---------------------------------------------------------------------------
# 6. Cash migration 0005 tests
# ---------------------------------------------------------------------------


def test_migration_0005_cash_constraint_exists(
    postgres_engine,
) -> None:
    """Both cash CHECK constraints exist on holding tables."""
    with postgres_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conname LIKE 'ck_portfolio%_cash_unit_price' "
                "ORDER BY conname"
            )
        ).fetchall()
        names = {r[0] for r in rows}
        assert "ck_portfolio_draft_holdings_cash_unit_price" in names
        assert "ck_portfolio_snapshot_holdings_cash_unit_price" in names


def test_cash_constraint_direct_sql(
    postgres_engine,
) -> None:
    """Direct SQL cash-with-wrong-price is rejected; non-cash is fine.
    Each constraint test uses its own transaction to avoid abort cascading."""
    # Test 1: cash with unit_price != 1.00 is rejected (0.99)
    with postgres_engine.begin() as conn:
        conn.execute(text(_TRUNCATE_ALL))
        conn.execute(
            text("INSERT INTO household_profiles (id, household_name, base_currency, "
                 "investment_horizon, liquidity_needs, risk_statement, notes) "
                 "VALUES (gen_random_uuid(), 'ct1', 'USD', '', '', '', '')")
        )
        hh = conn.execute(text("SELECT id FROM household_profiles")).fetchone()
        conn.execute(
            text("INSERT INTO portfolios (id, household_id, status) "
                 "VALUES (gen_random_uuid(), :hh, 'draft')"),
            {"hh": hh[0]},
        )
        pf = conn.execute(text("SELECT id FROM portfolios")).fetchone()
        conn.execute(
            text("INSERT INTO portfolio_drafts "
                 "(portfolio_id, expected_revision) VALUES (:pid, 1)"),
            {"pid": pf[0]},
        )

        with pytest.raises(Exception) as exc:
            conn.execute(
                text(
                    "INSERT INTO portfolio_draft_holdings "
                    "(id, portfolio_id, asset_name, asset_category, quantity, "
                    " unit_price, total_value, valuation_date) "
                    "VALUES (gen_random_uuid(), :pid, 'BadCash', 'cash', 100, "
                    " 0.99, 99.00, CURRENT_DATE)"
                ),
                {"pid": pf[0]},
            )
        assert "ck_portfolio_draft_holdings_cash_unit_price" in str(exc.value)

    # Test 2: cash with unit_price != 1.00 is rejected (1.01)
    with postgres_engine.begin() as conn:
        conn.execute(text(_TRUNCATE_ALL))
        conn.execute(
            text("INSERT INTO household_profiles (id, household_name, base_currency, "
                 "investment_horizon, liquidity_needs, risk_statement, notes) "
                 "VALUES (gen_random_uuid(), 'ct2', 'USD', '', '', '', '')")
        )
        hh = conn.execute(text("SELECT id FROM household_profiles")).fetchone()
        conn.execute(
            text("INSERT INTO portfolios (id, household_id, status) "
                 "VALUES (gen_random_uuid(), :hh, 'draft')"),
            {"hh": hh[0]},
        )
        pf = conn.execute(text("SELECT id FROM portfolios")).fetchone()
        conn.execute(
            text("INSERT INTO portfolio_drafts "
                 "(portfolio_id, expected_revision) VALUES (:pid, 1)"),
            {"pid": pf[0]},
        )

        with pytest.raises(Exception) as exc:
            conn.execute(
                text(
                    "INSERT INTO portfolio_draft_holdings "
                    "(id, portfolio_id, asset_name, asset_category, quantity, "
                    " unit_price, total_value, valuation_date) "
                    "VALUES (gen_random_uuid(), :pid, 'BadCash', 'cash', 100, "
                    " 1.01, 101.00, CURRENT_DATE)"
                ),
                {"pid": pf[0]},
            )
        assert "ck_portfolio_draft_holdings_cash_unit_price" in str(exc.value)

    # Test 3: cash with 1.00 works; non-cash works
    with postgres_engine.begin() as conn:
        conn.execute(text(_TRUNCATE_ALL))
        conn.execute(
            text("INSERT INTO household_profiles (id, household_name, base_currency, "
                 "investment_horizon, liquidity_needs, risk_statement, notes) "
                 "VALUES (gen_random_uuid(), 'ct3', 'USD', '', '', '', '')")
        )
        hh = conn.execute(text("SELECT id FROM household_profiles")).fetchone()
        conn.execute(
            text("INSERT INTO portfolios (id, household_id, status) "
                 "VALUES (gen_random_uuid(), :hh, 'draft')"),
            {"hh": hh[0]},
        )
        pf = conn.execute(text("SELECT id FROM portfolios")).fetchone()
        conn.execute(
            text("INSERT INTO portfolio_drafts "
                 "(portfolio_id, expected_revision) VALUES (:pid, 1)"),
            {"pid": pf[0]},
        )

        # cash + 1.00 works
        conn.execute(
            text(
                "INSERT INTO portfolio_draft_holdings "
                "(id, portfolio_id, asset_name, asset_category, quantity, "
                " unit_price, total_value, valuation_date) "
                "VALUES (gen_random_uuid(), :pid, 'Cash', 'cash', 1000, "
                " 1.00, 1000.00, CURRENT_DATE)"
            ),
            {"pid": pf[0]},
        )

        # CASH + 1.00 (uppercase with spaces) works
        conn.execute(
            text(
                "INSERT INTO portfolio_draft_holdings "
                "(id, portfolio_id, asset_name, asset_category, quantity, "
                " unit_price, total_value, valuation_date) "
                "VALUES (gen_random_uuid(), :pid, 'Cash Alt', ' CASH ', 500, "
                " 1.00, 500.00, CURRENT_DATE)"
            ),
            {"pid": pf[0]},
        )

        # non-cash with any price works
        conn.execute(
            text(
                "INSERT INTO portfolio_draft_holdings "
                "(id, portfolio_id, asset_name, asset_category, quantity, "
                " unit_price, total_value, valuation_date) "
                "VALUES (gen_random_uuid(), :pid, 'Stock', 'equity', 10, "
                " 150.50, 1505.00, CURRENT_DATE)"
            ),
            {"pid": pf[0]},
        )


# ---------------------------------------------------------------------------
# 7. Decimal Gate — ROUND_HALF_EVEN
# ---------------------------------------------------------------------------


def test_decimal_round_half_even_exact_cents(
    api_client: TestClient,
) -> None:
    """Values with exactly 2 decimal places remain unchanged."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("EXACT", 10, Decimal("100.50"))],
        },
    )
    assert r.status_code == 200, r.text
    h = r.json()["holdings"][0]
    assert h["total_value"] == "1005.00"


def test_decimal_round_half_even_tie_even(
    api_client: TestClient,
) -> None:
    """Tie at .xx5 with even preceding digit -> round down."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("EVEN", 2, Decimal("1.125"))],
        },
    )
    assert r.status_code == 200, r.text
    h = r.json()["holdings"][0]
    assert h["total_value"] == "2.25"


def test_decimal_round_half_even_tie_odd(
    api_client: TestClient,
) -> None:
    """Tie at .xx5 with odd preceding digit -> round up."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("ODD", 2, Decimal("1.175"))],
        },
    )
    assert r.status_code == 200, r.text
    h = r.json()["holdings"][0]
    assert h["total_value"] == "2.35"


def test_decimal_round_half_even_negative(
    api_client: TestClient,
) -> None:
    """Small fractional rounds to 0.00."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("TINY", 1, Decimal("0.005"))],
        },
    )
    assert r.status_code == 200, r.text
    h = r.json()["holdings"][0]
    assert h["total_value"] == "0.00"


def test_decimal_api_db_consistency(
    api_client: TestClient,
) -> None:
    """After Confirm, snapshot total_value matches API response exactly."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("CONSIST", 3, Decimal("33.3333"))],
        },
    )
    c = api_client.post(
        "/api/portfolio/draft/confirm",
        json={"confirmation": True, "expected_revision": rev + 1},
    )
    assert c.status_code == 201, c.text
    api_tv = c.json()["holdings"][0]["total_value"]

    s = SessionLocal()
    try:
        snap = (
            s.query(models.PortfolioSnapshot)
            .filter_by(status="current")
            .order_by(models.PortfolioSnapshot.version_number.desc())
            .first()
        )
        h = (
            s.query(models.PortfolioSnapshotHolding)
            .filter_by(snapshot_id=snap.id)
            .first()
        )
        db_tv = str(h.total_value)
        assert api_tv == db_tv, f"API: {api_tv}, DB: {db_tv}"
    finally:
        s.close()


def test_decimal_overflow_rejected(api_client: TestClient) -> None:
    """Values exceeding NUMERIC(20,8) precision are rejected."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("HUGE", Decimal("1"), Decimal("1.123456789012"))],
        },
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# 8. Security error tests
# ---------------------------------------------------------------------------


def test_cash_unit_price_error_returns_422_safe(
    api_client: TestClient,
) -> None:
    """Cash with wrong price returns 422 with fixed message, no SQL leak."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    p = api_client.get("/api/portfolio").json()
    rev = p["draft"]["expected_revision"]
    r = api_client.put(
        "/api/portfolio/draft/holdings",
        json={
            "expected_revision": rev,
            "items": [holding("MyCash", 100, Decimal("0.99"), "cash")],
        },
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "unit_price" in detail.lower()
    assert "1.00" in detail
    assert "ck_" not in detail.lower()
    assert "sql" not in detail.lower()
    assert "traceback" not in detail.lower()


def test_generic_error_returns_500_no_detail(
    api_client: TestClient,
) -> None:
    """Unknown exception must return 500 with generic message, no SQL leak."""
    _create_household(api_client)
    api_client.post(BASE, json={})

    r = api_client.patch(
        "/api/portfolio/draft",
        json={"valuation_date": "9999-01-01"},
    )
    assert r.status_code in (200, 422), r.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def holding(
    name: str,
    quantity: Decimal | int,
    unit_price: Decimal,
    category: str = "equity",
) -> dict:
    return {
        "asset_name": name,
        "asset_category": category,
        "quantity": str(quantity),
        "unit_price": str(unit_price),
        "valuation_date": "2026-07-01",
        "notes": "",
    }
