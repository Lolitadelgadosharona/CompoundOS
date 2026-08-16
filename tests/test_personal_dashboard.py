"""PE-001 Sprint 1 tests — Personal Dashboard (Home)."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.decision_lifecycle import DecisionBridgeService

pytestmark = pytest.mark.postgres


def _setup_household(db_session):
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


def _seed_pending_decision(db_session, household_id):
    """Seed a pending (draft) decision so the Home shows real data."""
    policy_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policies (id, household_id) VALUES (:id, :hh)"
    ), {"id": policy_id, "hh": household_id})
    vid = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policy_versions (id, policy_id,"
        " version_number, status, published_at, objectives, time_horizon,"
        " liquidity, diversification, contribution_policy,"
        " rebalancing_policy, prohibited_assets, leverage_policy,"
        " decision_process, notes)"
        " VALUES (:id, :pid, 1, 'published', NOW(), 'o', 'h',"
        " '', '', '', '', '', '', 'd', '')"
    ), {"id": vid, "pid": policy_id})
    db_session.execute(text(
        "UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"
    ), {"id": vid})
    idea = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title, status,"
        " source, confidence, created_at)"
        " VALUES (:id, :hh, 'AAPL', 'draft', 'owner', 'LOW', NOW())"
    ), {"id": idea, "hh": household_id})
    rr = uuid4()
    db_session.execute(text(
        "INSERT INTO committee_review_requests (id, investment_idea_id,"
        " status, requested_by, created_at)"
        " VALUES (:id, :iid, 'pending', 'owner', NOW())"
    ), {"id": rr, "iid": idea})
    req = uuid4()
    db_session.execute(text(
        "INSERT INTO research_requests (id, review_request_id, status,"
        " created_at, updated_at)"
        " VALUES (:id, :rrid, 'completed', NOW(), NOW())"
    ), {"id": req, "rrid": rr})
    run_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number, status,"
        " created_at, updated_at)"
        " VALUES (:id, :req, 1, 'completed', NOW(), NOW())"
    ), {"id": run_id, "req": req})
    db_session.execute(text(
        "INSERT INTO investment_memos (id, run_id, memo, synthesis_model,"
        " confidence_score, confidence_level, recommendation, generated_at)"
        " VALUES (:id, :rid, :memo, 'synthesis', 75, 'MEDIUM', 'BUY', NOW())"
    ), {"id": uuid4(), "rid": run_id,
        "memo": json.dumps({"thesis": "Strong moat", "risks": ["Valuation"]})})
    DecisionBridgeService.create_decision_draft(
        db_session, run_id, "AAPL", "BUY", "Strong moat", ["Valuation"],
    )
    db_session.commit()


class TestPersonalDashboard:
    def test_dashboard_renders(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        assert "Richard AI Family Office" in r.text
        assert "Wealth Overview" in r.text
        assert "AI Daily Brief" in r.text
        assert "Pending Decisions" in r.text

    def test_empty_database_graceful(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        assert "Not configured" in r.text            # cash position
        assert "No active alerts" in r.text
        assert "No pending decisions" in r.text
        assert "Daily Brief will be available in PE-002" in r.text

    def test_no_secrets_exposed(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        lower = r.text.lower()
        for secret in ("password", "gho_", "sk-ss-v1", "sk-ai-v1",
                       "x-api-key", "api_key="):
            assert secret not in lower, f"exposed secret: {secret}"

    def test_no_ai_calls(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        # Rendering the dashboard must not create any AI execution log.
        count = db_session.execute(text(
            "SELECT COUNT(*) FROM llm_execution_log"
        )).scalar()
        assert count == 0

    def test_existing_data_appears(self, api_client, db_session):
        hh = _setup_household(db_session)
        _seed_pending_decision(db_session, hh)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        assert "AAPL" in r.text          # pending decision symbol
        assert "BUY" in r.text           # recommendation
        assert "75" in r.text            # confidence (memo confidence_score)


class TestSettingsPage:
    def test_settings_renders(self, api_client):
        r = api_client.get("/settings")
        assert r.status_code == 200
        assert "Observability" in r.text
        assert "System Readiness" in r.text
