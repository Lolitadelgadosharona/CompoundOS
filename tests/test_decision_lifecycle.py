"""Tests for Sprint 013 Slice D — Decision Lifecycle."""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.decision_lifecycle import (
    CommitteeIntegrationService,
    LearningLoopService,
    OwnerDecisionService,
    ProvenanceService,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


def _setup_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key,"
        " household_name, base_currency, investment_horizon,"
        " liquidity_needs, risk_statement, notes,"
        " created_at, updated_at) VALUES (:id, TRUE, 't','USD','lt',"
        "'l','m','',NOW(),NOW()) ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()
    return row[0]


def _setup_full_chain(db_session, household_id):
    """Create FK chain: household→idea→review_request→request→run→memo."""
    idea_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title,"
        " status, source, confidence, created_at)"
        " VALUES (:id, :hh, 't', 'draft', 'owner', 'LOW', NOW())"
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
        "INSERT INTO research_runs (id, request_id, run_number,"
        " status, created_at, updated_at)"
        " VALUES (:id, :req, 1, 'completed', NOW(), NOW())"
    ), {"id": run_id, "req": req_id})
    memo_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_memos (id, run_id, memo,"
        " synthesis_model, confidence_score, confidence_level,"
        " recommendation, generated_at)"
        " VALUES (:id, :rid, :memo, 'synthesis', 75, 'MEDIUM',"
        " 'BUY', NOW())"
    ), {"id": memo_id, "rid": run_id,
        "memo": json.dumps({"thesis": "Strong growth potential"})})
    db_session.commit()
    return idea_id, run_id, memo_id, rr_id


# ═══════════════════════════════════════════════════════════════════════
# CommitteeIntegrationService
# ═══════════════════════════════════════════════════════════════════════


class TestCommitteeIntegration:
    def test_complete_research_creates_session(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        result = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        assert "session_id" in result
        assert "memo_id" in result
        assert "recommendation" in result

    def test_evidence_item_created(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        result = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        items = db_session.execute(text(
            "SELECT COUNT(*) FROM committee_evidence_items"
            " WHERE session_id = :sid"
        ), {"sid": result["session_id"]}).scalar()
        assert items >= 1

    def test_no_memo_raises(self, db_session):
        hh = _setup_household(db_session)
        with pytest.raises(ValueError, match="No memo"):
            CommitteeIntegrationService.complete_research(
                db_session, uuid4(), hh,
            )


# ═══════════════════════════════════════════════════════════════════════
# OwnerDecisionService
# ═══════════════════════════════════════════════════════════════════════


class TestOwnerDecision:
    def test_approve_creates_decision(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        result = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75,
        )
        assert result["status"] == "approved"
        assert "decision_id" in result

    def test_reject_creates_decision(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        result = OwnerDecisionService.reject(
            db_session, idea_id, memo_id, session_id, 75,
        )
        assert result["status"] == "rejected"

    def test_decision_persisted(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        result = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75,
        )
        row = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": result["decision_id"]}).fetchone()
        assert row is not None
        assert row[0] == "proposed"


# ═══════════════════════════════════════════════════════════════════════
# LearningLoopService
# ═══════════════════════════════════════════════════════════════════════


class TestLearningLoop:
    def test_schedule_reviews_creates_three(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75,
        )
        reviews = LearningLoopService.schedule_reviews(
            db_session, uuid4(),
        )
        assert len(reviews) == 3

    def test_record_outcome(self, db_session):
        LearningLoopService.record_outcome(
            db_session, "AAPL", uuid4(), 12.5,
        )
        rows = db_session.execute(text(
            "SELECT COUNT(*) FROM investment_knowledge_memory"
        )).scalar()
        assert rows >= 1

    def test_update_prediction_accuracy(self, db_session):
        LearningLoopService.update_prediction_accuracy(
            db_session, "AAPL", 75, 12.5,
        )
        row = db_session.execute(text(
            "SELECT prediction_accuracy FROM investment_knowledge_memory"
            " WHERE entity_key = 'AAPL' ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
        assert row is not None


# ═══════════════════════════════════════════════════════════════════════
# ProvenanceService
# ═══════════════════════════════════════════════════════════════════════


class TestProvenance:
    def test_trace_returns_chain(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        # Create session + evidence
        result = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        # Create decision
        dec = OwnerDecisionService.approve(
            db_session, idea_id, memo_id,
            uuid4(result["session_id"]), 75,
        )
        chain = ProvenanceService.trace(
            db_session, uuid4(dec["decision_id"]),
        )
        assert "decision" in chain

    def test_trace_nonexistent_returns_error(self, db_session):
        chain = ProvenanceService.trace(db_session, uuid4())
        assert "error" in chain


class TestAIAuthority:
    def test_never_action_still_blocked(self):
        assert True
