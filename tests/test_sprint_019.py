"""Tests for Sprint 019 — Investment Operating System."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Portfolio Review Workflow
# ═══════════════════════════════════════════════════════════════════════

class TestReviewWorkflow:
    def test_monthly_review(self):
        r = client.get("/api/os/review/monthly")
        assert r.status_code == 200
        data = r.json()
        assert "portfolio_value" in data
        assert "actions_needed" in data
        assert "decision_reviews" in data
        assert "needs_attention" in data

    def test_quarterly_review(self):
        r = client.get("/api/os/review/quarterly")
        assert r.status_code == 200
        data = r.json()
        assert "headline" in data
        assert "recommendations" in data

    def test_stale_flag_in_review(self):
        r = client.get("/api/os/review/monthly")
        data = r.json()
        stale = [d for d in data["decision_reviews"] if d.get("stale")]
        assert len(stale) >= 1

    def test_no_trade_in_review(self):
        r = client.get("/api/os/review/monthly")
        text = str(r.json()).lower()
        assert "trade" not in text
        assert "broker" not in text


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Risk Monitoring
# ═══════════════════════════════════════════════════════════════════════

class TestRiskMonitoring:
    def test_stress_scenarios(self):
        r = client.get("/api/os/risk/stress")
        assert r.status_code == 200
        data = r.json()
        assert len(data["scenarios"]) == 4

    def test_alerts_no_breach(self):
        r = client.post("/api/os/risk/alerts", json={
            "positions": [
                {"symbol": "AAPL", "weight_pct": 14},
                {"symbol": "MSFT", "weight_pct": 12},
            ],
            "beta": 1.2, "drawdown": 8.5,
        })
        assert r.status_code == 200
        alerts = r.json()["alerts"]
        # No position >25%, so no position alerts
        has_pos_alert = any("Position" in a["rule"] for a in alerts)
        assert not has_pos_alert

    def test_alerts_position_breach(self):
        r = client.post("/api/os/risk/alerts", json={
            "positions": [
                {"symbol": "AAPL", "weight_pct": 28},
            ],
            "beta": 1.8, "drawdown": 18,
        })
        data = r.json()
        alerts = data["alerts"]
        assert len(alerts) >= 1
        assert "AAPL" in str(alerts)

    def test_scenario_severity_levels(self):
        r = client.get("/api/os/risk/stress")
        scenarios = r.json()["scenarios"]
        severities = {s["severity"] for s in scenarios}
        assert "critical" in severities


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Capital Allocation Assistant
# ═══════════════════════════════════════════════════════════════════════

class TestAllocation:
    def test_deploy_guidance(self):
        r = client.post("/api/os/allocate/deploy", json={
            "amount": 50000,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["recommendations"]) == 3
        assert "disclaimer" in data
        assert "not financial advice" in data["disclaimer"].lower()

    def test_sell_options(self):
        r = client.post("/api/os/allocate/sell", json={
            "amount": 30000,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["options"]) >= 1

    def test_no_execution_capability(self):
        r = client.post("/api/os/allocate/deploy", json={
            "amount": 10000,
        })
        text = str(r.json()).lower()
        assert "trade" not in text
        assert "autonomous" not in text
        disclaimer = r.json().get("disclaimer", "")
        assert "guidance only" in disclaimer.lower()


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Family Office Reporting
# ═══════════════════════════════════════════════════════════════════════

class TestReporting:
    def test_monthly_report(self):
        r = client.post("/api/os/report/generate", json={
            "report_type": "monthly", "format": "dashboard",
        })
        assert r.status_code == 200
        data = r.json()
        assert "holdings" in data["sections"]

    def test_quarterly_report(self):
        r = client.post("/api/os/report/generate", json={
            "report_type": "quarterly", "format": "dashboard",
        })
        assert r.status_code == 200
        assert "Q3" in r.json()["title"]

    def test_csv_export(self):
        r = client.get("/api/os/report/csv/monthly")
        assert r.status_code == 200
        assert "Symbol" in r.text
        assert "AAPL" in r.text


class TestNoTrading:
    def test_all_os_endpoints_no_trade(self):
        for path in ["/api/os/review/monthly",
                     "/api/os/risk/stress"]:
            r = client.get(path)
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
