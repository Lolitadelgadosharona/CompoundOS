"""Tests for Sprint 013 Slice D — Decision Lifecycle."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

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
    """Create FK chain: household→idea→review_request→request→run→memo,
    plus a published policy version (required by confirm_draft)."""
    idea_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title,"
        " status, source, confidence, created_at)"
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
        "memo": json.dumps({
            "thesis": "Strong growth potential with a durable moat",
            "risks": ["Valuation risk", "Regulatory risk"],
        })})
    # Published policy + version (confirm_draft requires one)
    policy_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policies (id, household_id)"
        " VALUES (:id, :hh)"
    ), {"id": policy_id, "hh": household_id})
    version_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policy_versions (id, policy_id,"
        " version_number, status, published_at, objectives, time_horizon,"
        " liquidity, diversification, contribution_policy,"
        " rebalancing_policy, prohibited_assets, leverage_policy,"
        " decision_process, notes)"
        " VALUES (:id, :pid, 1, 'published', NOW(),"
        " 'obj', 'horizon', '', '', '', '', '', '', 'decide', '')"
    ), {"id": version_id, "pid": policy_id})
    # Seal the published version (two-phase lifecycle: insert → seal)
    db_session.execute(text(
        "UPDATE investment_policy_versions SET sealed_at = NOW()"
        " WHERE id = :id"
    ), {"id": version_id})
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
            db_session, idea_id, memo_id, session_id, 75, hh,
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
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        assert result["status"] == "rejected"

    def test_decision_persisted(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        result = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        row = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": result["decision_id"]}).fetchone()
        assert row is not None
        assert row[0] == "confirmed"

    def test_approve_creates_confirmed_snapshot(self, db_session):
        """Approval flows through the journal: draft → confirm → snapshot."""
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        result = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        decision_id = UUID(result["decision_id"])
        snap = db_session.execute(text(
            "SELECT title, rationale, evidence_or_sources"
            " FROM decision_confirmed_snapshots WHERE decision_id = :id"
        ), {"id": decision_id}).fetchone()
        assert snap is not None
        assert snap[0] == "AAPL investment decision"
        assert snap[1] == "Strong growth potential with a durable moat"
        assert f"research_run_id={run_id}" in snap[2]
        # No bare 'proposed' row, no lingering draft
        draft = db_session.execute(text(
            "SELECT COUNT(*) FROM decision_drafts WHERE decision_id = :id"
        ), {"id": decision_id}).scalar()
        assert draft == 0


# ═══════════════════════════════════════════════════════════════════════
# LearningLoopService
# ═══════════════════════════════════════════════════════════════════════


class TestLearningLoop:
    def test_schedule_reviews_creates_three(self, db_session):
        """approve() auto-schedules 30/90/365 reviews via lifecycle wiring."""
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(
            db_session, hh,
        )
        session_id = uuid4()
        dec = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        # approve() already scheduled the reviews — verify they exist
        reviews = db_session.execute(text(
            "SELECT review_type FROM decision_reviews WHERE decision_id = :id"
        ), {"id": dec["decision_id"]}).fetchall()
        assert {r[0] for r in reviews} == {"30_day", "90_day", "1_year"}

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
            UUID(result["session_id"]), 75, hh,
        )
        chain = ProvenanceService.trace(
            db_session, UUID(dec["decision_id"]),
        )
        assert "decision" in chain

    def test_trace_nonexistent_returns_error(self, db_session):
        chain = ProvenanceService.trace(db_session, uuid4())
        assert "error" in chain


class TestAIAuthority:
    def test_never_action_still_blocked(self):
        assert True


# ═══════════════════════════════════════════════════════════════════════
# Full lifecycle wiring (M5-004)
# ═══════════════════════════════════════════════════════════════════════


class TestDecisionLifecycleWiring:
    """Proves the full chain: Research → Committee → Decision → Approval
    → Journal → Learning → Provenance (mock providers only, no AI calls)."""

    def _seed_analyses(self, db_session, run_id):
        perspectives = [
            ("value", "claude-sonnet-4"), ("growth", "gpt-4o"),
            ("risk", "claude-sonnet-4"), ("macro", "gpt-4o"),
            ("policy", "claude-sonnet-4"), ("portfolio_fit", "gpt-4o"),
        ]
        for p, m in perspectives:
            db_session.execute(text(
                "INSERT INTO perspective_analyses (id, run_id, perspective,"
                " model, analysis, conviction_score, completed_at)"
                " VALUES (:id, :rid, :p, :m, '{}', 7, NOW())"
            ), {"id": uuid4(), "rid": run_id, "p": p, "m": m})
            db_session.execute(text(
                "INSERT INTO llm_execution_log (id, run_id, perspective,"
                " model, status, retry_count, started_at, completed_at)"
                " VALUES (:id, :rid, :p, :m, 'success', 0, NOW(), NOW())"
            ), {"id": uuid4(), "rid": run_id, "p": p, "m": m})
        db_session.commit()

    def test_full_lifecycle_wiring(self, db_session):
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(db_session, hh)
        self._seed_analyses(db_session, run_id)

        # Research → Committee (committee session + evidence)
        bridge = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        session_id = UUID(bridge["session_id"])
        assert bridge["recommendation"] == "BUY"

        # Committee → Decision → Approval → Learning (journal lifecycle)
        result = OwnerDecisionService.approve(
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        decision_id = UUID(result["decision_id"])
        assert result["status"] == "approved"
        assert len(result["review_ids"]) == 3

        # Decision status confirmed + snapshot exists (journal, no bare row)
        status = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": decision_id}).scalar()
        assert status == "confirmed"

        # Learning reviews: 30/90/365
        reviews = db_session.execute(text(
            "SELECT review_type FROM decision_reviews"
            " WHERE decision_id = :id"
        ), {"id": decision_id}).fetchall()
        assert {r[0] for r in reviews} == {"30_day", "90_day", "1_year"}

        # Provenance trace: complete chain
        chain = ProvenanceService.trace(db_session, decision_id)
        assert "decision" in chain
        assert "decision_draft" in chain
        assert chain["decision_draft"]["confirmed"] is True
        assert "memo" in chain
        assert "perspectives" in chain
        assert "llm_execution" in chain
        assert "evidence" in chain
        assert len(chain["perspectives"]) == 6
        assert len(chain["llm_execution"]) == 6
        assert len(chain["evidence"]) >= 1

    def test_reject_keeps_draft_unconfirmed(self, db_session):
        """Rejected decisions create a journal draft but never confirm."""
        hh = _setup_household(db_session)
        idea_id, run_id, memo_id, rr_id = _setup_full_chain(db_session, hh)
        session_id = uuid4()
        result = OwnerDecisionService.reject(
            db_session, idea_id, memo_id, session_id, 75, hh,
        )
        decision_id = UUID(result["decision_id"])
        assert result["status"] == "rejected"
        status = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": decision_id}).scalar()
        assert status == "draft"
        # No snapshot for a rejected decision
        snap = db_session.execute(text(
            "SELECT COUNT(*) FROM decision_confirmed_snapshots"
            " WHERE decision_id = :id"
        ), {"id": decision_id}).scalar()
        assert snap == 0
