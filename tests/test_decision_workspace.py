"""PE-004A tests — Decision Workspace + Committee UI read-model."""

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
    return hh


def _seed_workspace(db_session, household_id):
    """Seed idea → review → request → run → memo → perspectives → draft."""
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

    memo_json = json.dumps({
        "thesis": "Strong moat",
        "bull_case": {"narrative": "AI growth tailwind"},
        "bear_case": {"narrative": "Valuation risk"},
        "risks": ["Valuation", "Competition"],
        "valuation": {"method": "DCF"},
        "committee": {
            "consensus": "BUY",
            "disagreements": [
                {"perspective": "risk", "conviction": 4, "deviation": -2.0},
            ],
            "perspectives": {},
        },
        "portfolio_impact": {"allocation": "5% position"},
        "guardian_impact": {"compliant": True},
        "evidence": {"sources": ["Analyst coverage", "Insider transactions"]},
    })
    db_session.execute(text(
        "INSERT INTO investment_memos (id, run_id, memo, synthesis_model,"
        " confidence_score, confidence_level, recommendation, generated_at)"
        " VALUES (:id, :rid, CAST(:memo AS jsonb), 'synthesis', 83,"
        " 'HIGH', 'BUY', NOW())"
    ), {"id": uuid4(), "rid": run_id, "memo": memo_json})

    for perspective in ("value", "growth", "risk", "macro", "policy",
                        "portfolio_fit"):
        analysis = json.dumps({
            "perspective": perspective,
            "thesis": f"{perspective} thesis",
            "evidence": f"{perspective} evidence",
            "conviction_score": 7,
        })
        db_session.execute(text(
            "INSERT INTO perspective_analyses (id, run_id, perspective,"
            " model, prompt_version, requested_model, resolved_model,"
            " provider, actual_model, analysis, conviction_score,"
            " started_at, completed_at)"
            " VALUES (:id, :rid, :p, 'm', 1, 'm', 'm', 'p', 'm',"
            " CAST(:a AS jsonb), 7, NOW(), NOW())"
        ), {"id": uuid4(), "rid": run_id, "p": perspective, "a": analysis})

    decision, _draft = DecisionBridgeService.create_decision_draft(
        db_session, run_id, "AAPL", "BUY", "Strong moat", ["Valuation"],
    )
    db_session.commit()
    return decision.id


class TestDecisionWorkspaceAPI:
    def test_workspace_missing_404(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get(f"/api/decision-workspace/{uuid4()}")
        assert r.status_code == 404

    def test_workspace_returns_summary_and_committee(self, api_client,
                                                      db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/api/decision-workspace/{decision_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "draft"
        assert data["recommendation"] == "BUY"
        assert data["confidence"] == 83
        assert len(data["perspectives"]) == 6
        assert data["memo"]["bull_case"] == "AI growth tailwind"
        assert data["memo"]["bear_case"] == "Valuation risk"
        assert "Valuation" in data["memo"]["risks"]
        assert data["memo"]["consensus"] == "BUY"
        assert data["memo"]["disagreements"][0]["perspective"] == "risk"
        assert data["memo"]["guardian_impact"] == "Policy compliant: True"
        assert data["memo"]["portfolio_impact"] is not None
        # PE-004C: evidence coverage + missing evidence + confidence
        assert data["evidence_coverage"]["total"] == 6
        assert data["evidence_coverage"]["with_evidence"] == 6
        assert "Analyst coverage" in data["missing_evidence"]
        assert "value" in data["confidence_explanation"]["contributors"]


class TestDecisionWorkspacePage:
    def test_page_renders(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        assert "Decision Summary" in r.text
        assert "Investment Committee" in r.text
        assert "Memo Summary" in r.text
        assert "BUY" in r.text

    def test_page_no_raw_json(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        # No raw JSON blobs surfaced.
        assert '"narrative"' not in r.text
        assert '"conviction_score"' not in r.text

    def test_page_has_decision_actions(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        assert "approve-btn" in r.text
        assert "reject-btn" in r.text

    def test_page_shows_disagreement(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        assert "Disagreement" in r.text
        assert "Committee Consensus" in r.text

    def test_page_shows_impact(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        assert "Portfolio &amp; Guardian Impact" in r.text
        assert "Policy compliant: True" in r.text

    def test_page_shows_evidence_sections(self, api_client, db_session):
        hh = _setup_household(db_session)
        decision_id = _seed_workspace(db_session, hh)
        r = api_client.get(f"/decision/{decision_id}")
        assert r.status_code == 200
        assert "Evidence Coverage" in r.text
        assert "Missing Evidence" in r.text
        assert "Confidence Explanation" in r.text
        assert "Analyst coverage" in r.text


class TestDecisionsListUX:
    def test_decisions_page_has_visible_feedback(self, api_client, db_session):
        hh = _setup_household(db_session)
        _seed_workspace(db_session, hh)
        r = api_client.get("/decisions")
        assert r.status_code == 200
        # Review link to the workspace + JS-based decision buttons
        assert "/decision/" in r.text
        assert "decision-btn" in r.text
        # no more invisible hx-swap="none" on the approve/reject buttons
        assert "hx-swap=\"none\"" not in r.text
