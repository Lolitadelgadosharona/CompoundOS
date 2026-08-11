"""Tests for Sprint 023 — Real World Operation."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Household
# ═══════════════════════════════════════════════════════════════════════

class TestHousehold:
    def test_snapshot(self):
        r = client.post("/api/household/snapshot", json={
            "investments": 1_250_000, "cash": 85_000,
            "real_estate": 600_000, "debt": 200_000,
            "expenses": 12_000, "income": 18_000,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["net_worth"] == 1_735_000

    def test_emergency_fund_green(self):
        r = client.post("/api/household/snapshot", json={
            "investments": 500_000, "cash": 100_000,
            "real_estate": 400_000, "expenses": 8_000,
        })
        data = r.json()
        assert data["emergency_fund_months"] > 6
        assert data["emergency_fund_status"] == "green"

    def test_emergency_fund_red(self):
        r = client.post("/api/household/snapshot", json={
            "investments": 500_000, "cash": 15_000,
            "real_estate": 400_000, "expenses": 10_000,
        })
        data = r.json()
        assert data["emergency_fund_status"] == "red"

    def test_savings_rate(self):
        r = client.post("/api/household/snapshot", json={
            "investments": 1_000_000, "cash": 50_000,
            "real_estate": 500_000, "expenses": 8_000,
            "income": 12_000,
        })
        data = r.json()
        assert data["savings_rate_pct"] > 20


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Calibration
# ═══════════════════════════════════════════════════════════════════════

class TestCalibration:
    def test_report_generation(self):
        r = client.post("/api/household/calibration/report", json={
            "outcomes": [
                {"symbol": "AAPL", "correct": True, "return_pct": 12},
                {"symbol": "JNJ", "correct": False, "return_pct": -5},
                {"symbol": "MSFT", "correct": True, "return_pct": 22},
            ],
            "perspective_data": {
                "value": {"correct": 8, "total": 10},
                "growth": {"correct": 6, "total": 10},
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall_accuracy"] > 0.5
        assert data["biggest_hit"]["return"] == 22

    def test_empty_outcomes(self):
        r = client.post("/api/household/calibration/report", json={
            "outcomes": [],
        })
        assert r.status_code == 200
        assert r.json()["overall_accuracy"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Wealth Planning
# ═══════════════════════════════════════════════════════════════════════

class TestWealthPlanning:
    def test_retirement_projection(self):
        r = client.post("/api/household/planning/retirement", json={
            "age": 45, "retire_age": 65, "savings": 500_000,
            "contribution": 2_000,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["projected_value"] > 500_000
        assert "disclaimer" in data

    def test_college_projection(self):
        r = client.post("/api/household/planning/college", json={
            "child_age": 10, "savings": 50_000,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["years_to_college"] == 8
        assert data["total_4yr_cost"] > 100_000

    def test_estate_checklist(self):
        r = client.get("/api/household/planning/estate")
        assert r.status_code == 200
        data = r.json()
        assert "will" in data
        assert "disclaimer" in data


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Behavior
# ═══════════════════════════════════════════════════════════════════════

class TestBehavior:
    def test_insights(self):
        r = client.post("/api/household/behavior/insights", json={
            "decisions": [
                {"symbol": "AAPL", "sector": "tech"},
                {"symbol": "MSFT", "sector": "tech"},
                {"symbol": "JNJ", "sector": "healthcare"},
            ],
            "approvals": 8, "rejections": 2,
            "avg_latency_days": 5,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["insights"]) >= 2

    def test_no_profiling(self):
        r = client.post("/api/household/behavior/insights", json={
            "decisions": [], "approvals": 0, "rejections": 0,
        })
        text = str(r.json()).lower()
        assert "profile" not in text
        assert "psycho" not in text


class TestNoTrading:
    def test_no_trade_in_household(self):
        for path in ["/api/household/snapshot",
                     "/api/household/planning/estate"]:
            r = client.get(path) if "estate" in path else client.post(
                path, json={"investments": 100, "cash": 50,
                            "real_estate": 200},
            )
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
