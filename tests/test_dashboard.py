"""Tests for Sprint 014 Slice B — Owner Dashboard (real-data wiring)."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _seed_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement,"
        " notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        " ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()
    return db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()[0]


def _seed_memo(db_session, household_id):
    """Minimal idea → review → request → run → memo chain for memo page."""
    idea_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title, status,"
        " source, confidence, created_at)"
        " VALUES (:id, :hh, 'AAPL', 'draft', 'owner', 'LOW', NOW())"
    ), {"id": idea_id, "hh": household_id})
    rr_id = uuid4()
    db_session.execute(text(
        "INSERT INTO committee_review_requests (id, investment_idea_id,"
        " status, requested_by, created_at)"
        " VALUES (:id, :iid, 'pending', 'owner', NOW())"
    ), {"id": rr_id, "iid": idea_id})
    req_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_requests (id, review_request_id, status,"
        " created_at, updated_at)"
        " VALUES (:id, :rrid, 'completed', NOW(), NOW())"
    ), {"id": req_id, "rrid": rr_id})
    run_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number, status,"
        " created_at, updated_at)"
        " VALUES (:id, :req, 1, 'completed', NOW(), NOW())"
    ), {"id": run_id, "req": req_id})
    memo_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_memos (id, run_id, memo, synthesis_model,"
        " confidence_score, confidence_level, recommendation, generated_at)"
        " VALUES (:id, :rid, :memo, 'synthesis', 75, 'MEDIUM', 'BUY', NOW())"
    ), {"id": memo_id, "rid": run_id,
        "memo": json.dumps({"thesis": "Strong moat"})})
    db_session.commit()
    return memo_id


class TestDashboardRoutes:
    def test_dashboard_loads(self, api_client, db_session):
        _seed_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        assert "Richard AI Family Office" in r.text

    def test_research_loads(self, api_client):
        r = api_client.get("/research")
        assert r.status_code == 200
        assert "Research" in r.text

    def test_memo_loads(self, api_client, db_session):
        hh = _seed_household(db_session)
        memo_id = _seed_memo(db_session, hh)
        r = api_client.get(f"/memo/{memo_id}")
        assert r.status_code == 200
        assert "Investment Memo" in r.text
        assert "BUY" in r.text

    def test_memo_missing_returns_404(self, api_client):
        r = api_client.get(f"/memo/{uuid4()}")
        assert r.status_code == 404

    def test_memo_invalid_id_returns_400(self, api_client):
        r = api_client.get("/memo/not-a-uuid")
        assert r.status_code == 400

    def test_decisions_loads(self, api_client, db_session):
        _seed_household(db_session)
        r = api_client.get("/decisions")
        assert r.status_code == 200
        assert "Committee Decisions" in r.text

    def test_learning_loads(self, api_client):
        r = api_client.get("/learning")
        assert r.status_code == 200
        assert "Learning Dashboard" in r.text


class TestDashboardAuth:
    def test_dashboard_no_auth_in_dev(self, api_client, db_session):
        """In development/test, dashboard is accessible without API key."""
        _seed_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200


class TestDashboardStructure:
    def test_navigation_present(self, api_client, db_session):
        _seed_household(db_session)
        for path in ["/dashboard", "/research", "/decisions", "/learning"]:
            r = api_client.get(path)
            assert "Richard AI Family Office" in r.text

    def test_no_trading_interface(self, api_client, db_session):
        _seed_household(db_session)
        for path in ["/dashboard", "/research", "/decisions", "/learning"]:
            r = api_client.get(path)
            assert "trade" not in r.text.lower()
            assert "broker" not in r.text.lower()
            assert "execute" not in r.text.lower()

    def test_html_renders(self, api_client, db_session):
        _seed_household(db_session)
        for path in ["/dashboard", "/research", "/decisions", "/learning"]:
            r = api_client.get(path)
            assert "text/html" in r.headers["content-type"]
