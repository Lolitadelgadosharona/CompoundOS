"""Tests for Sprint 015 — All slices."""

from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.pipeline_async import (
    PipelineProgressTracker,
    PipelineState,
)
from apps.api.services.validation_service import (
    VALIDATION_SYMBOLS,
    ValidationService,
)

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Dashboard Data Integration
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardData:
    def test_summary_endpoint(self):
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        assert "net_worth" in data
        assert "allocation" in data

    def test_research_list_empty(self):
        r = client.get("/api/dashboard/research/list")
        assert r.status_code == 200
        data = r.json()
        assert "requests" in data

    def test_pending_decisions(self):
        r = client.get("/api/dashboard/decisions/pending")
        assert r.status_code == 200
        data = r.json()
        assert "pending" in data

    def test_decision_history(self):
        r = client.get("/api/dashboard/decisions/history")
        assert r.status_code == 200

    def test_learning_metrics(self):
        r = client.get("/api/dashboard/learning/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "accuracy" in data
        # perspectives + outcomes are real (derived from recorded outcomes;
        # empty when none exist), not a hardcoded six-entry list.
        assert isinstance(data.get("perspectives"), list)
        assert isinstance(data.get("outcomes"), list)

    def test_empty_state_all_endpoints_200(self):
        for path in [
            "/api/dashboard/summary",
            "/api/dashboard/research/list",
            "/api/dashboard/decisions/pending",
            "/api/dashboard/decisions/history",
            "/api/dashboard/learning/metrics",
        ]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Async Pipeline UX
# ═══════════════════════════════════════════════════════════════════════

class TestPipelineProgress:
    def test_create_progress(self):
        rid = uuid4()
        p = PipelineProgressTracker.create(rid)
        assert p.state == PipelineState.PENDING
        assert p.progress_pct == 0

    def test_progress_state_transitions(self):
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        p = PipelineProgressTracker.update(rid, PipelineState.RUNNING,
                                            perspective_count=3)
        assert p is not None
        assert p.state == PipelineState.RUNNING
        assert p.progress_pct == 55  # 25 + 3*10

    def test_complete_sets_confidence(self):
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        PipelineProgressTracker.update(rid, PipelineState.COMPLETE,
                                       memo_id="m1", confidence=72)
        p = PipelineProgressTracker.get(rid)
        assert p is not None
        assert p.is_complete
        assert p.memo_id == "m1"
        assert p.confidence == 72

    def test_failed_state(self):
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        PipelineProgressTracker.update(rid, PipelineState.FAILED,
                                       error="Provider unavailable")
        p = PipelineProgressTracker.get(rid)
        assert p is not None
        assert p.is_failed
        assert p.error == "Provider unavailable"

    def test_progress_pct_complete_is_100(self):
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        PipelineProgressTracker.update(rid, PipelineState.COMPLETE)
        p = PipelineProgressTracker.get(rid)
        assert p.progress_pct == 100

    def test_steps_tracking(self):
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        PipelineProgressTracker.add_step(rid, "Fetching market data")
        p = PipelineProgressTracker.get(rid)
        assert len(p.steps) == 1
        assert p.steps[0]["step"] == "Fetching market data"

    def test_get_nonexistent_returns_none(self):
        assert PipelineProgressTracker.get(uuid4()) is None

    def test_start_endpoint(self):
        r = client.post("/api/research/start",
                        json={"symbol": "AAPL"})
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert data["status"] == "pending"

    def test_status_endpoint_not_found(self):
        r = client.get(f"/api/research/{uuid4()}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "not_found"


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Real Investment Validation
# ═══════════════════════════════════════════════════════════════════════

class TestValidation:
    def test_symbols_list(self):
        assert len(VALIDATION_SYMBOLS) == 5
        assert "AAPL" in VALIDATION_SYMBOLS
        assert "JNJ" in VALIDATION_SYMBOLS

    def test_evaluate_empty_scores(self):
        report = ValidationService.evaluate("AAPL", "m1")
        assert report.symbol == "AAPL"
        assert report.overall == 5
        assert report.passed

    def test_evaluate_with_scores(self):
        scores = [
            ("thesis_clarity", 8, "Clear thesis"),
            ("evidence_quality", 6, "Adequate evidence"),
        ]
        report = ValidationService.evaluate("AAPL", "m1", scores)
        assert report.overall == 7
        assert report.recommendation == "Actionable"

    def test_evaluate_low_scores(self):
        scores = [("thesis_clarity", 3, "Weak")] * 5
        report = ValidationService.evaluate("AAPL", "m1", scores)
        assert report.overall == 3
        assert report.recommendation == "Insufficient"

    def test_batch_evaluate(self):
        reports = ValidationService.batch_evaluate()
        assert len(reports) == 5

    def test_summary(self):
        reports = [
            ValidationService.evaluate("AAPL", "m1",
                                       [("c", 8, "")]),
            ValidationService.evaluate("MSFT", "m2",
                                       [("c", 3, "")]),
        ]
        summary = ValidationService.summary(reports)
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1


# ═══════════════════════════════════════════════════════════════════════
# Slice D — No autonomous trading
# ═══════════════════════════════════════════════════════════════════════

class TestNoTrading:
    def test_research_start_returns_no_trade(self):
        r = client.post("/api/research/start",
                        json={"symbol": "AAPL"})
        data = r.json()
        assert "trade" not in str(data).lower()
        assert "execute" not in str(data).lower()
        assert "broker" not in str(data).lower()

    def test_status_returns_no_trade(self):
        r = client.post("/api/research/start",
                        json={"symbol": "AAPL"})
        rid = r.json()["run_id"]
        s = client.get(f"/api/research/{rid}/status")
        data = s.json()
        assert "trade" not in str(data).lower()
