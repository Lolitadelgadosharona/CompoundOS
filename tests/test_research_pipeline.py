"""Tests for Sprint 012 Slice B — Research Execution Pipeline."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from apps.api.services.research_pipeline import (
    ConfidenceEngine,
    EvidenceBundle,
    EvidenceCollector,
    LocalWorker,
    PerspectiveResult,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# WorkerQueue
# ═══════════════════════════════════════════════════════════════════════


class TestWorkerQueue:
    def test_local_worker_enqueues(self):
        results = []

        def task(x):
            results.append(x)

        worker = LocalWorker()
        worker.enqueue(task, 42)
        import time
        time.sleep(0.5)
        assert 42 in results


# ═══════════════════════════════════════════════════════════════════════
# EvidenceCollector
# ═══════════════════════════════════════════════════════════════════════


class TestEvidenceCollector:
    def test_collect_returns_bundle(self, db_session):
        collector = EvidenceCollector()
        bundle = collector.collect(db_session, uuid4())
        assert isinstance(bundle, EvidenceBundle)

    def test_evidence_has_market_data(self, db_session):
        collector = EvidenceCollector()
        bundle = collector.collect(db_session, uuid4())
        assert isinstance(bundle.market_data, dict)

    def test_evidence_has_portfolio_context(self, db_session):
        collector = EvidenceCollector()
        bundle = collector.collect(db_session, uuid4())
        assert isinstance(bundle.portfolio_context, dict)

    def test_evidence_has_guardian_status(self, db_session):
        collector = EvidenceCollector()
        bundle = collector.collect(db_session, uuid4())
        assert isinstance(bundle.guardian_status, dict)


# ═══════════════════════════════════════════════════════════════════════
# ConfidenceEngine
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceEngine:
    def test_returns_versioned_output(self):
        engine = ConfidenceEngine()
        result = engine.calculate([], EvidenceBundle())
        assert result.model_version == 1
        assert result.level in ("HIGH", "MEDIUM", "LOW")
        assert result.recommendation in ("BUY", "HOLD", "PASS")
        assert "evidence_quality" in result.breakdown

    def test_score_increases_with_perspectives(self):
        engine = ConfidenceEngine()
        perspectives = [
            PerspectiveResult(perspective="value", model="c",
                              prompt_version=1, analysis={},
                              conviction_score=8, success=True),
            PerspectiveResult(perspective="growth", model="c",
                              prompt_version=1, analysis={},
                              conviction_score=7, success=True),
        ]
        result = engine.calculate(perspectives, EvidenceBundle())
        assert result.score > 0

    def test_empty_gives_low(self):
        engine = ConfidenceEngine()
        result = engine.calculate([], EvidenceBundle())
        assert result.score == 0
        assert result.level == "LOW"

    def test_breakdown_has_all_dimensions(self):
        engine = ConfidenceEngine()
        result = engine.calculate([], EvidenceBundle())
        for dim in ["evidence_quality", "thesis_clarity", "risk_completeness",
                     "policy_alignment", "data_freshness", "historical_precedent"]:
            assert dim in result.breakdown


# ═══════════════════════════════════════════════════════════════════════
# AI Authority
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_no_trading_path(self):
        import inspect

        from apps.api.services.research_pipeline import (
            PerspectiveExecutor,
        )
        for cls in [PerspectiveExecutor]:
            src = inspect.getsource(cls)
            forbidden = ["trade", "broker", "approve_investment",
                         "execute_trade", "connect_broker"]
            for word in forbidden:
                assert word not in src.lower()
