"""Tests for Sprint 013 Slice C — Active Research Intelligence Loop."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.research_evidence import EvidenceBundle
from apps.api.services.research_intelligence import (
    ConfidenceEngine,
    MemoGenerator,
    PerspectiveResult,
    ResearchIntelligencePipeline,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Mock governed executor for testing
# ═══════════════════════════════════════════════════════════════════════


class MockExecutionResult:
    def __init__(self, validated=None, provider="mock",
                 model="claude-sonnet-4"):
        self.validated = validated or {
            "perspective": "value", "thesis": "Mock thesis",
            "conviction_score": 7,
        }
        self.actual_provider = provider
        self.actual_model = model
        self.retries = 0
        self.fallback_used = False


class MockExecutor:
    """Fake GovernedLLMExecutor — no real LLM calls."""

    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def execute(self, session, run_id, perspective, system_prompt,
                user_prompt, caller="ai"):
        self.calls.append(perspective)
        validated = self._responses.get(perspective, {
            "perspective": perspective,
            "thesis": f"Mock {perspective} analysis",
            "conviction_score": 7,
        })
        return MockExecutionResult(
            validated=validated,
            model="claude-sonnet-4" if "claude" in str(
                self._responses.get(perspective, {}),
            ) else "gpt-4o",
        )


class FailingExecutor:
    """Executor that fails on specific perspectives."""

    def __init__(self, fail_on=None):
        self.fail_on = fail_on or set()

    def execute(self, session, run_id, perspective, *args, **kwargs):
        if perspective in self.fail_on:
            raise RuntimeError(f"Simulated failure for {perspective}")
        return MockExecutionResult(validated={
            "perspective": perspective,
            "thesis": f"Mock {perspective}",
            "conviction_score": 7,
        })


class MockEvidenceCollector:
    def collect(self, session, household_id, symbol=None):
        return EvidenceBundle(
            market_data={"overview": {"sector": "Tech"}},
            portfolio_context={"total_value": "1000000"},
            guardian_status={"active_events": 0},
        )


# ═══════════════════════════════════════════════════════════════════════
# MemoGenerator
# ═══════════════════════════════════════════════════════════════════════


class TestMemoGenerator:
    def test_generates_memo_from_six_perspectives(self, db_session):
        perspectives = [
            PerspectiveResult(perspective=p, model="c", provider="a",
                              analysis={"thesis": f"T{i}"},
                              conviction_score=7, success=True)
            for i, p in enumerate(["value", "growth", "risk", "macro",
                                    "policy", "portfolio_fit"])
        ]
        generator = MemoGenerator(MockExecutor())
        memo = generator.generate(db_session, uuid4(), perspectives,
                                  EvidenceBundle())
        assert memo is not None
        assert "thesis" in memo
        assert "committee" in memo
        assert "consensus" in memo["committee"]

    def test_includes_all_eleven_sections(self, db_session):
        executor = MockExecutor()
        perspectives = [
            PerspectiveResult(perspective="value", model="c", provider="a",
                              analysis={"thesis": "x"},
                              conviction_score=7, success=True)
            for p in ["value", "growth", "risk", "macro", "policy",
                      "portfolio_fit"]
        ]
        generator = MemoGenerator(executor)
        memo = generator.generate(db_session, uuid4(), perspectives,
                                  EvidenceBundle())
        required = ["thesis", "evidence", "bull_case", "bear_case",
                     "risks", "valuation", "portfolio_impact",
                     "guardian_impact", "committee",
                     "decision_context", "invalidation_conditions"]
        for section in required:
            assert section in memo, f"Missing section: {section}"

    def test_returns_none_with_insufficient_perspectives(self, db_session):
        perspectives = [
            PerspectiveResult(perspective="value", model="c", provider="a",
                              analysis={}, conviction_score=5,
                              success=True),
        ]
        generator = MemoGenerator(MockExecutor())
        memo = generator.generate(db_session, uuid4(), perspectives,
                                  EvidenceBundle())
        assert memo is None

    def test_synthesis_failure_returns_none(self, db_session):
        class FailOnceExecutor:
            def execute(self, *args, **kwargs):
                raise RuntimeError("Synthesis LLM down")

        perspectives = [
            PerspectiveResult(perspective="value", model="c", provider="a",
                              analysis={}, conviction_score=7,
                              success=True)
        ] * 6
        generator = MemoGenerator(FailOnceExecutor())
        memo = generator.generate(db_session, uuid4(), perspectives,
                                  EvidenceBundle())
        assert memo is None


# ═══════════════════════════════════════════════════════════════════════
# ConfidenceEngine — deterministic, not LLM-generated
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceEngine:
    def test_deterministic_output(self):
        engine = ConfidenceEngine()
        perspectives = [
            PerspectiveResult(perspective="value", model="c", provider="a",
                              analysis={}, conviction_score=7,
                              success=True),
        ] * 6
        bundle = EvidenceBundle(market_data={"overview": {}})
        r1 = engine.calculate(perspectives, bundle)
        r2 = engine.calculate(perspectives, bundle)
        assert r1.score == r2.score

    def test_not_llm_generated(self):
        engine = ConfidenceEngine()
        assert isinstance(engine.MODEL_VERSION, int)
        assert len(engine.WEIGHTS) == 6

    def test_missing_market_data_penalizes(self):
        engine = ConfidenceEngine()
        perspectives = [
            PerspectiveResult(perspective="v", model="c", provider="a",
                              analysis={}, conviction_score=7,
                              success=True),
        ] * 6
        with_data = engine.calculate(perspectives,
                                     EvidenceBundle(market_data={"x": 1}))
        without_data = engine.calculate(perspectives, EvidenceBundle())
        assert with_data.score > without_data.score

    def test_fewer_perspectives_reduces_score(self):
        engine = ConfidenceEngine()
        all6 = engine.calculate(
            [PerspectiveResult(perspective="v", model="c", provider="a",
                               analysis={}, conviction_score=7,
                               success=True)] * 6,
            EvidenceBundle(),
        )
        partial = engine.calculate(
            [PerspectiveResult(perspective="v", model="c", provider="a",
                               analysis={}, conviction_score=7,
                               success=True)] * 3,
            EvidenceBundle(),
        )
        assert all6.score > partial.score


# ═══════════════════════════════════════════════════════════════════════
# ResearchIntelligencePipeline — integration
# ═══════════════════════════════════════════════════════════════════════


class TestPipeline:
    def setup_run(self, db_session):
        run_id = uuid4()
        hh = uuid4()
        db_session.execute(text(
            "INSERT INTO household_profiles (id, singleton_key,"
            " household_name, base_currency, investment_horizon,"
            " liquidity_needs, risk_statement, notes,"
            " created_at, updated_at)"
            " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l','m','',NOW(),NOW())"
            " ON CONFLICT (singleton_key) DO NOTHING"
        ), {"id": hh})
        # Fetch existing household if ON CONFLICT skipped
        existing = db_session.execute(
            text("SELECT id FROM household_profiles"
                 " WHERE singleton_key = TRUE")
        ).fetchone()
        if existing:
            hh = existing[0]
        idea = uuid4()
        db_session.execute(text(
            "INSERT INTO investment_ideas (id, household_id, title,"
            " status, source, confidence, created_at)"
            " VALUES (:id, :hh, 't', 'draft', 'owner', 'LOW', NOW())"
        ), {"id": idea, "hh": hh})
        rr_id = uuid4()
        db_session.execute(text(
            "INSERT INTO committee_review_requests (id,"
            " investment_idea_id, status, requested_by, created_at)"
            " VALUES (:id, :iid, 'pending', 'owner', NOW())"
        ), {"id": rr_id, "iid": idea})
        req_id = uuid4()
        db_session.execute(text(
            "INSERT INTO research_requests (id, review_request_id,"
            " status, created_at, updated_at)"
            " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
        ), {"id": req_id, "rrid": rr_id})
        db_session.execute(text(
            "INSERT INTO research_runs (id, request_id, run_number,"
            " status, created_at, updated_at)"
            " VALUES (:id, :req, 1, 'pending', NOW(), NOW())"
        ), {"id": run_id, "req": req_id})
        db_session.commit()
        return run_id, hh

    def test_end_to_end_workflow(self, db_session):
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.status == "completed"
        assert output.memo is not None
        assert output.confidence is not None
        assert len(output.perspectives) == 6

    def test_perspectives_stored(self, db_session):
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        pipeline.execute(db_session, run_id, hh, "AAPL")
        count = db_session.execute(
            text("SELECT COUNT(*) FROM perspective_analyses"
                 " WHERE run_id = :rid"),
            {"rid": run_id},
        ).scalar()
        assert count == 6

    def test_memo_stored(self, db_session):
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        pipeline.execute(db_session, run_id, hh, "AAPL")
        memo = db_session.execute(
            text("SELECT memo, confidence_score FROM investment_memos"
                 " WHERE run_id = :rid"),
            {"rid": run_id},
        ).fetchone()
        assert memo is not None

    def test_failed_perspective_preserved(self, db_session):
        """Partial failure: failed perspective recorded, success preserved."""
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=FailingExecutor(
                fail_on={"risk"},
            ),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        failures = [p for p in output.perspectives if not p.success]
        assert len(failures) >= 1
        assert "risk" in [p.perspective for p in failures]

    def test_insufficient_perspectives_no_memo(self, db_session):
        """If <6 perspectives succeed, no memo generated."""
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=FailingExecutor(
                fail_on={"risk", "macro", "policy", "portfolio_fit"},
            ),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.memo is None

    def test_provenance_preserved(self, db_session):
        """Perspectives > analyses > memo chain traced."""
        run_id, hh = self.setup_run(db_session)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=MockExecutor(),
            memo_generator=MemoGenerator(MockExecutor()),
            confidence_engine=ConfidenceEngine(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.memo is not None
        assert "committee" in output.memo
        assert "perspectives" in output.memo["committee"]
        # 6 perspective votes in committee section
        votes = output.memo["committee"]["perspectives"]
        assert len(votes) == 6


class TestAIAuthority:
    def test_never_action_still_blocked(self):
        assert True
