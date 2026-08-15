"""M5-005 tests — real-data dashboard + real research execution wiring."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.dashboard_research import DashboardResearchService
from apps.api.services.dashboard_service import (
    learning_metrics,
    list_decision_history,
    list_memo,
    list_pending_decisions_detail,
)
from apps.api.services.decision_lifecycle import (
    CommitteeIntegrationService,
    DecisionBridgeService,
    OwnerDecisionService,
    _symbol_for_run,
)
from apps.api.services.research_evidence import EvidenceBundle
from apps.api.services.research_pipeline_factory import build_research_pipeline

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ── Mocks (no real AI) ──────────────────────────────────────────────────


class MockExecutionResult:
    def __init__(self, validated=None, provider="mock", model="gpt-4o"):
        self.validated = validated or {
            "thesis": "Mock thesis", "conviction_score": 7,
        }
        self.actual_provider = provider
        self.actual_model = model
        self.requested_model = model
        self.resolved_model = model
        self.retries = 0
        self.fallback_used = False


class MockExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, session, run_id, perspective, system_prompt,
                user_prompt, caller="ai", max_output_tokens=None,
                requested_model=None):
        self.calls.append(perspective)
        return MockExecutionResult(validated={
            "thesis": f"Mock {perspective} thesis",
            "conviction_score": 7,
            "risks": ["Valuation risk", "Regulatory risk"],
        })


class MockEvidenceCollector:
    def collect(self, session, household_id, symbol=None):
        return EvidenceBundle(
            market_data={"overview": {"sector": "Tech"}},
            portfolio_context={"total_value": "1000000"},
            guardian_status={"active_events": 0},
        )


# ── Fixtures ────────────────────────────────────────────────────────────


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


def _setup_run(db_session, household_id):
    """idea → review → request → run chain (no memo yet)."""
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
        " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
    ), {"id": req_id, "rrid": rr_id})
    run_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number, status,"
        " created_at, updated_at)"
        " VALUES (:id, :req, 1, 'pending', NOW(), NOW())"
    ), {"id": run_id, "req": req_id})
    db_session.commit()
    return idea_id, run_id


def _seed_policy(db_session, household_id):
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
        " VALUES (:id, :pid, 1, 'published', NOW(), 'obj', 'horizon',"
        " '', '', '', '', '', '', 'decide', '')"
    ), {"id": vid, "pid": policy_id})
    db_session.execute(text(
        "UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"
    ), {"id": vid})
    db_session.commit()


# ── Phase B: factory + real execution ───────────────────────────────────


class TestPipelineFactory:
    def test_factory_builds_working_pipeline(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        pipeline = build_research_pipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.status == "completed"
        assert output.memo is not None

    def test_factory_creates_memo_and_perspectives(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        pipeline = build_research_pipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
        )
        pipeline.execute(db_session, run_id, hh, "AAPL")
        memo_count = db_session.execute(text(
            "SELECT COUNT(*) FROM investment_memos WHERE run_id = :rid"
        ), {"rid": run_id}).scalar()
        assert memo_count == 1


# ── Phase A/C: research → committee → decision ──────────────────────────


class TestResearchToDecision:
    def test_create_request_creates_fk_chain(self, db_session):
        hh = _setup_household(db_session)
        result = DashboardResearchService.create_request(
            db_session, "AAPL", hh,
        )
        run_id = UUID(result["run_id"])
        req = db_session.execute(text(
            "SELECT review_request_id FROM research_requests"
            " WHERE id = (SELECT request_id FROM research_runs WHERE id = :rid)"
        ), {"rid": run_id}).fetchone()
        assert req is not None
        assert result["status"] == "pending"

    def test_symbol_for_run(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        assert _symbol_for_run(db_session, run_id) == "AAPL"

    def test_full_lifecycle_through_services(self, db_session):
        hh = _setup_household(db_session)
        _seed_policy(db_session, hh)
        idea_id, run_id = _setup_run(db_session, hh)

        # Run the real pipeline (mock executor)
        pipeline = build_research_pipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.memo is not None

        # Research → Committee
        bridge = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        assert bridge["recommendation"] is not None

        # Committee → Decision Draft
        memo_row = db_session.execute(text(
            "SELECT memo, recommendation FROM investment_memos WHERE id = :id"
        ), {"id": UUID(bridge["memo_id"])}).fetchone()
        memo_json = memo_row[0] if isinstance(memo_row[0], dict) \
            else json.loads(memo_row[0])
        decision, draft = DecisionBridgeService.create_decision_draft(
            db_session, run_id, "AAPL", memo_row[1] or "HOLD",
            memo_json.get("thesis", ""), memo_json.get("risks", []),
        )
        assert decision.status == "draft"

        # Owner approval (confirm_decision)
        result = OwnerDecisionService.confirm_decision(
            db_session, decision.id,
        )
        assert result["status"] == "approved"
        assert len(result["review_ids"]) == 3

        # Journal: confirmed + snapshot + no draft
        status = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": decision.id}).scalar()
        assert status == "confirmed"
        snap = db_session.execute(text(
            "SELECT COUNT(*) FROM decision_confirmed_snapshots"
            " WHERE decision_id = :id"
        ), {"id": decision.id}).scalar()
        assert snap == 1


# ── Phase C: owner approve/reject endpoints (service layer) ─────────────


class TestOwnerActions:
    def _make_draft(self, db_session):
        hh = _setup_household(db_session)
        _seed_policy(db_session, hh)
        _idea_id, run_id = _setup_run(db_session, hh)
        db_session.execute(text(
            "INSERT INTO investment_memos (id, run_id, memo, synthesis_model,"
            " confidence_score, confidence_level, recommendation, generated_at)"
            " VALUES (:id, :rid, :memo, 'synthesis', 75, 'MEDIUM', 'BUY', NOW())"
        ), {"id": uuid4(), "rid": run_id,
            "memo": json.dumps({"thesis": "T", "risks": ["R"]})})
        db_session.commit()
        decision, _draft = DecisionBridgeService.create_decision_draft(
            db_session, run_id, "AAPL", "BUY", "T", ["R"],
        )
        return decision

    def test_reject_removes_draft(self, db_session):
        decision = self._make_draft(db_session)
        result = OwnerDecisionService.reject_decision(db_session, decision.id)
        assert result["status"] == "rejected"
        # decision discarded (journal)
        row = db_session.execute(text(
            "SELECT COUNT(*) FROM decisions WHERE id = :id"
        ), {"id": decision.id}).scalar()
        assert row == 0

    def test_confirm_creates_reviews(self, db_session):
        decision = self._make_draft(db_session)
        result = OwnerDecisionService.confirm_decision(db_session, decision.id)
        assert result["status"] == "approved"
        reviews = db_session.execute(text(
            "SELECT review_type FROM decision_reviews WHERE decision_id = :id"
        ), {"id": decision.id}).fetchall()
        assert {r[0] for r in reviews} == {"30_day", "90_day", "1_year"}


# ── Phase A/D: dashboard read helpers ───────────────────────────────────


class TestDashboardReads:
    def _seed_full(self, db_session):
        hh = _setup_household(db_session)
        _seed_policy(db_session, hh)
        _idea_id, run_id = _setup_run(db_session, hh)
        memo_id = uuid4()
        db_session.execute(text(
            "INSERT INTO investment_memos (id, run_id, memo, synthesis_model,"
            " confidence_score, confidence_level, recommendation, generated_at)"
            " VALUES (:id, :rid, :memo, 'synthesis', 75, 'MEDIUM', 'BUY', NOW())"
        ), {"id": memo_id, "rid": run_id,
            "memo": json.dumps({
                "thesis": "Strong moat", "risks": ["Valuation"],
                "bull_case": {"narrative": "AI growth"},
                "bear_case": {"narrative": "Regulatory"},
                "guardian_impact": {"compliant": True},
            })})
        db_session.commit()
        decision, _draft = DecisionBridgeService.create_decision_draft(
            db_session, run_id, "AAPL", "BUY", "Strong moat", ["Valuation"],
        )
        return hh, run_id, memo_id, decision.id

    def test_list_memo_reads_real_data(self, db_session):
        _hh, _run_id, memo_id, _did = self._seed_full(db_session)
        memo = list_memo(db_session, memo_id)
        assert memo is not None
        assert memo["thesis"] == "Strong moat"
        assert memo["recommendation"] == "BUY"
        assert memo["confidence"] == 75

    def test_pending_and_history(self, db_session):
        hh, _run_id, _memo_id, decision_id = self._seed_full(db_session)
        pending = list_pending_decisions_detail(db_session, hh)
        assert any(p["decision_id"] == str(decision_id) for p in pending)
        assert pending[0]["symbol"] == "AAPL"
        assert pending[0]["recommendation"] == "BUY"

        # confirm, then it appears in history
        OwnerDecisionService.confirm_decision(db_session, decision_id)
        pending_after = list_pending_decisions_detail(db_session, hh)
        assert all(p["decision_id"] != str(decision_id)
                   for p in pending_after)
        history = list_decision_history(db_session, hh)
        assert any(h["symbol"] == "AAPL" for h in history)

    def test_learning_metrics_reads_reviews(self, db_session):
        hh, _run_id, _memo_id, decision_id = self._seed_full(db_session)
        OwnerDecisionService.confirm_decision(db_session, decision_id)
        metrics = learning_metrics(db_session)
        assert metrics["review_count"] == 3
        assert metrics["accuracy"] >= 0.0
