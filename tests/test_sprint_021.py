"""Tests for Sprint 021 — Real Operation & Calibration."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Decision Accuracy
# ═══════════════════════════════════════════════════════════════════════

class TestAccuracy:
    def test_record_outcomes(self):
        r = client.post("/api/ops-real/accuracy/outcomes", json={
            "decisions": [
                {"symbol": "AAPL", "decision": "BUY",
                 "confidence": 75, "date": "2026-06-01",
                 "decision_price": 175, "days_elapsed": 60},
                {"symbol": "JNJ", "decision": "HOLD",
                 "confidence": 40, "date": "2026-04-01",
                 "decision_price": 155, "days_elapsed": 90},
            ],
            "current_prices": {"AAPL": 195, "JNJ": 148},
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["outcomes"]) == 2
        assert len(data["metrics"]) == 3

    def test_direction_correct(self):
        r = client.post("/api/ops-real/accuracy/outcomes", json={
            "decisions": [
                {"symbol": "AAPL", "decision": "BUY",
                 "confidence": 75, "date": "2026-06-01",
                 "decision_price": 175, "days_elapsed": 60},
            ],
            "current_prices": {"AAPL": 195},
        })
        outcomes = r.json()["outcomes"]
        assert outcomes[0]["direction_correct"] is True

    def test_perspective_accuracy(self):
        r = client.post("/api/ops-real/accuracy/perspectives", json={
            "perspectives": [
                {"perspective": "Value", "correct": 8, "total": 10},
                {"perspective": "Growth", "correct": 6, "total": 10},
                {"perspective": "Risk", "correct": 9, "total": 10},
            ],
        })
        data = r.json()["perspectives"]
        assert data[0]["accuracy"] == 0.8


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Knowledge Compounding
# ═══════════════════════════════════════════════════════════════════════

class TestKnowledge:
    def test_cross_ref_no_past(self):
        r = client.post("/api/ops-real/knowledge/cross-ref", json={
            "symbol": "AAPL", "current_thesis": "Strong growth",
            "past_memos": [],
        })
        data = r.json()
        assert data["contradiction"] is False
        assert "No prior analysis" in data["context_blurb"]

    def test_cross_ref_consistent(self):
        r = client.post("/api/ops-real/knowledge/cross-ref", json={
            "symbol": "AAPL", "current_thesis": "Continued growth",
            "past_memos": [
                {"thesis": "Growth potential", "date": "2026-05",
                 "confidence": 75, "recommendation": "BUY"},
            ],
        })
        data = r.json()
        assert "Prior analysis" in data["context_blurb"]

    def test_cross_ref_contradiction(self):
        r = client.post("/api/ops-real/knowledge/cross-ref", json={
            "symbol": "AAPL",
            "current_thesis": "Deteriorating fundamentals — SELL",
            "past_memos": [
                {"thesis": "Strong buy", "date": "2026-05",
                 "confidence": 80, "recommendation": "BUY"},
            ],
        })
        data = r.json()
        assert data["contradiction"] is True


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Portfolio Validation
# ═══════════════════════════════════════════════════════════════════════

class TestPortfolio:
    def test_valid_csv(self):
        r = client.post("/api/ops-real/portfolio/import", json={
            "rows": [
                {"symbol": "AAPL", "shares": "100",
                 "cost_basis": "175", "asset_type": "stock"},
                {"symbol": "VOO", "shares": "50",
                 "cost_basis": "450", "asset_type": "etf"},
            ],
            "expected_total": 40000,
        })
        data = r.json()
        assert data["imported"] == 2
        assert data["total_value"] == 40000.0

    def test_missing_field(self):
        r = client.post("/api/ops-real/portfolio/import", json={
            "rows": [{"symbol": "AAPL", "shares": "100"}],
        })
        data = r.json()
        assert data["skipped"] >= 1

    def test_total_mismatch(self):
        r = client.post("/api/ops-real/portfolio/import", json={
            "rows": [
                {"symbol": "AAPL", "shares": "100",
                 "cost_basis": "175", "asset_type": "stock"},
            ],
            "expected_total": 25000,  # Actual is 175*100=17500
        })
        data = r.json()
        assert len(data["errors"]) >= 1

    def test_currency_flag(self):
        r = client.post("/api/ops-real/portfolio/import", json={
            "rows": [
                {"symbol": "NVO", "shares": "100",
                 "cost_basis": "120", "asset_type": "stock",
                 "currency": "DKK"},
            ],
        })
        data = r.json()
        assert len(data["currency_flags"]) >= 1


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Workflow Automation
# ═══════════════════════════════════════════════════════════════════════

class TestWorkflow:
    def test_reminders(self):
        r = client.get("/api/ops-real/workflow/reminders")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tasks"]) == 3

    def test_snapshot_is_auto(self):
        r = client.get("/api/ops-real/workflow/reminders")
        tasks = r.json()["tasks"]
        snap = [t for t in tasks if t["action"] == "snapshot"]
        assert len(snap) == 1
        assert snap[0]["auto_execute"] is True

    def test_research_is_reminder_only(self):
        r = client.get("/api/ops-real/workflow/reminders")
        tasks = r.json()["tasks"]
        research = [t for t in tasks
                    if t["action"] == "research_reminder"]
        assert research[0]["auto_execute"] is False


class TestNoTrading:
    def test_no_trade_in_real_ops(self):
        for path in ["/api/ops-real/accuracy/outcomes",
                     "/api/ops-real/workflow/reminders"]:
            r = client.get(path) if "reminders" in path else client.post(
                path, json={"decisions": [], "current_prices": {}},
            )
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
