"""PE-003 tests — Personal Investment Policy setup."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.decision_lifecycle import DecisionBridgeService
from apps.api.services.readiness_service import readiness_status

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


def _setup_payload():
    return {
        "investment_goal": "Long term wealth compounding",
        "risk_preference": "Growth",
        "investment_horizon": "10+ years",
        "max_single_position_pct": 15,
        "min_cash_pct": 10,
        "principles": ("Focus on high quality businesses, long-term "
                       "compounding, avoid speculation."),
    }


def _seed_decision_chain(db_session, household_id):
    """Seed idea → review → request → run → memo → decision draft
    (NO policy — that's the point of PE-003)."""
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
    decision, _draft = DecisionBridgeService.create_decision_draft(
        db_session, run_id, "AAPL", "BUY", "Strong moat", ["Valuation"],
    )
    db_session.commit()
    return decision.id


class TestPolicyReadiness:
    def test_empty_household_has_no_policy(self, db_session):
        _setup_household(db_session)
        status = readiness_status(db_session)
        assert status["checks"]["policy_published"] is False


class TestPolicySetupEndpoint:
    def test_setup_creates_and_publishes(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/policies/setup", json=_setup_payload())
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "published"
        assert body["version_number"] >= 1

    def test_published_policy_appears_in_readiness(self, api_client, db_session):
        _setup_household(db_session)
        api_client.post("/api/policies/setup", json=_setup_payload())
        status = readiness_status(db_session)
        assert status["checks"]["policy_published"] is True

    def test_setup_rejects_invalid_payload(self, api_client, db_session):
        _setup_household(db_session)
        payload = _setup_payload()
        payload["investment_goal"] = ""
        r = api_client.post("/api/policies/setup", json=payload)
        assert r.status_code == 422


class TestDecisionApproveWithPolicy:
    def test_approve_with_policy_succeeds(self, api_client, db_session):
        hh = _setup_household(db_session)
        api_client.post("/api/policies/setup", json=_setup_payload())
        decision_id = _seed_decision_chain(db_session, hh)
        r = api_client.post(f"/api/decisions/{decision_id}/approve")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_decisions_page_shows_policy_guidance(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/decisions")
        assert r.status_code == 200
        assert "Investment Policy required before approval" in r.text
        assert "/settings/investment-policy" in r.text

    def test_no_ai_calls(self, api_client, db_session):
        _setup_household(db_session)
        api_client.post("/api/policies/setup", json=_setup_payload())
        count = db_session.execute(text(
            "SELECT COUNT(*) FROM llm_execution_log"
        )).scalar()
        assert count == 0


class TestInvestmentPolicyPage:
    def test_page_renders(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/settings/investment-policy")
        assert r.status_code == 200
        assert "Investment Policy" in r.text
        assert "No published investment policy" in r.text

    def test_page_shows_published(self, api_client, db_session):
        _setup_household(db_session)
        api_client.post("/api/policies/setup", json=_setup_payload())
        r = api_client.get("/settings/investment-policy")
        assert r.status_code == 200
        assert "Published" in r.text
