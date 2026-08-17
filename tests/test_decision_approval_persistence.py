"""Decision approval persistence fix tests.

Verifies that POST /api/decisions/{id}/approve actually PERSISTS the
confirmation (status change + snapshot + reviews), not just returns 200.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.database import SessionLocal
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
    return hh


def _setup_payload():
    return {
        "investment_goal": "Long term wealth compounding",
        "risk_preference": "Growth",
        "investment_horizon": "10+ years",
        "max_single_position_pct": 15,
        "min_cash_pct": 10,
        "principles": "Focus on high quality businesses",
    }


def _seed_decision_chain(db_session, household_id):
    """Seed idea → review → request → run → memo → decision draft."""
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


def _fresh_query(sql, **params):
    s = SessionLocal()
    try:
        return s.execute(text(sql), params).fetchall()
    finally:
        s.close()


class TestApprovePersistence:
    def test_approve_persists_confirmation(self, api_client, db_session):
        hh = _setup_household(db_session)
        api_client.post("/api/policies/setup", json=_setup_payload())
        decision_id = _seed_decision_chain(db_session, hh)

        r = api_client.post(f"/api/decisions/{decision_id}/approve")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        # Fresh session — verify the confirmation actually persisted.
        rows = _fresh_query(
            "SELECT status FROM decisions WHERE id = :id", id=decision_id,
        )
        assert rows[0][0] == "confirmed"

        snaps = _fresh_query(
            "SELECT COUNT(*) FROM decision_confirmed_snapshots"
            " WHERE decision_id = :id", id=decision_id,
        )
        assert snaps[0][0] >= 1

        reviews = _fresh_query(
            "SELECT COUNT(*) FROM decision_reviews"
            " WHERE decision_id = :id", id=decision_id,
        )
        assert reviews[0][0] == 3
