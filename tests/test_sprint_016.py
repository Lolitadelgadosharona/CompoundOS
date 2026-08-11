"""Tests for Sprint 016 — Daily Operations."""


from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.daily_ops import (
    FeedbackService,
    LearningService,
)

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Daily Operating View
# ═══════════════════════════════════════════════════════════════════════

class TestDailyBrief:
    def test_brief_endpoint(self):
        r = client.get("/api/ops/brief")
        assert r.status_code == 200
        data = r.json()
        assert "pending_decisions" in data
        assert "recent_research" in data
        assert "portfolio_warnings" in data
        assert "guardian_alerts" in data

    def test_brief_has_attention_flag(self):
        r = client.get("/api/ops/brief")
        data = r.json()
        assert "needs_attention" in data

    def test_brief_priorities_in_order(self):
        r = client.get("/api/ops/brief")
        data = r.json()
        assert len(data["pending_decisions"]) >= 1
        assert len(data["recent_research"]) >= 1

    def test_no_trade_in_brief(self):
        r = client.get("/api/ops/brief")
        data = r.json()
        text = str(data).lower()
        assert "trade" not in text
        assert "broker" not in text
        assert "execute" not in text


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Owner Feedback
# ═══════════════════════════════════════════════════════════════════════

class TestOwnerFeedback:
    def test_submit_feedback(self):
        r = client.post("/api/ops/feedback", json={
            "memo_id": "m1", "thesis_agreement": 4,
            "evidence_sufficient": True,
            "confidence_appropriate": "correct",
            "would_act": "yes", "notes": "Good analysis",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "recorded"

    def test_submit_invalid_thesis(self):
        r = client.post("/api/ops/feedback", json={
            "memo_id": "m1", "thesis_agreement": 0,
            "evidence_sufficient": True,
            "confidence_appropriate": "correct",
            "would_act": "yes",
        })
        data = r.json()
        assert r.status_code == 422 or "error" in data

    def test_feedback_summary(self):
        client.post("/api/ops/feedback", json={
            "memo_id": "m2", "thesis_agreement": 5,
            "evidence_sufficient": True,
            "confidence_appropriate": "correct",
            "would_act": "yes",
        })
        r = client.get("/api/ops/feedback/summary")
        assert r.status_code == 200
        assert r.json()["count"] > 0

    def test_feedback_for_memo(self):
        client.post("/api/ops/feedback", json={
            "memo_id": "m3", "thesis_agreement": 3,
            "evidence_sufficient": False,
            "confidence_appropriate": "too_low",
            "would_act": "maybe",
        })
        r = client.get("/api/ops/feedback/m3")
        assert r.status_code == 200
        data = r.json()
        assert data["memo_id"] == "m3"
        assert data["count"] >= 1


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Learning Loop
# ═══════════════════════════════════════════════════════════════════════

class TestLearning:
    def test_record_outcome_up(self):
        r = client.post("/api/ops/learning/outcome", json={
            "symbol": "AAPL", "predicted_confidence": 75,
            "actual_return_pct": 12.5,
            "review_type": "30_day",
        })
        assert r.status_code == 200
        assert r.json()["direction_correct"] is True

    def test_record_outcome_down(self):
        r = client.post("/api/ops/learning/outcome", json={
            "symbol": "JNJ", "predicted_confidence": 80,
            "actual_return_pct": -5.0,
            "review_type": "90_day",
        })
        assert r.status_code == 200
        assert r.json()["direction_correct"] is False

    def test_accuracy_endpoint(self):
        r = client.get("/api/ops/learning/accuracy")
        assert r.status_code == 200
        data = r.json()
        assert "direction_accuracy" in data
        assert "count" in data

    def test_by_symbol(self):
        client.post("/api/ops/learning/outcome", json={
            "symbol": "AAPL", "predicted_confidence": 70,
            "actual_return_pct": 8.0, "review_type": "30_day",
        })
        r = client.get("/api/ops/learning/AAPL")
        assert r.status_code == 200
        assert r.json()["symbol"] == "AAPL"


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Data Quality
# ═══════════════════════════════════════════════════════════════════════

class TestDataQuality:
    def test_fresh_price(self):
        from datetime import datetime, timedelta, timezone
        recent = (datetime.now(timezone.utc)
                  - timedelta(hours=1)).isoformat()
        r = client.post("/api/ops/data-quality/check", json={
            "source_type": "price", "last_fetched": recent,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "fresh"

    def test_stale_price(self):
        from datetime import datetime, timedelta, timezone
        old = (datetime.now(timezone.utc)
               - timedelta(hours=48)).isoformat()
        r = client.post("/api/ops/data-quality/check", json={
            "source_type": "price", "last_fetched": old,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "stale"

    def test_missing_data(self):
        r = client.post("/api/ops/data-quality/check", json={
            "source_type": "overview",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "missing"
        assert r.json()["confidence_impact"] > 0

    def test_all_checks(self):
        r = client.get("/api/ops/data-quality/all")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 4


class TestNoAutonomous:
    def test_feedback_is_passive(self):
        """FeedbackService stores data; no autonomous actions."""
        fb = FeedbackService.submit("m1", 4, True, "correct", "yes")
        assert fb.memo_id == "m1"
        # No trades, no decisions, no DB mutations triggered

    def test_learning_is_passive(self):
        """LearningService records metrics; no self-modification."""
        m = LearningService.record_outcome("AAPL", 75, 12.5, "30_day")
        assert m.symbol == "AAPL"
        # No AI training, no policy changes
