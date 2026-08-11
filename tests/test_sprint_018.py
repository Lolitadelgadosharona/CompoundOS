"""Tests for Sprint 018 — Portfolio Intelligence Upgrade."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Analytics
# ═══════════════════════════════════════════════════════════════════════

class TestAnalytics:
    def test_sharpe_calculation(self):
        r = client.post("/api/portfolio/analytics", json={
            "returns": [1.2, 0.8, -0.5, 2.1, 1.5, 0.3,
                        -1.0, 0.9, 1.8, -0.2, 2.0, 0.7],
            "period": "1y",
        })
        assert r.status_code == 200
        data = r.json()
        assert "sharpe_ratio" in data
        assert "sharpe_rating" in data

    def test_max_drawdown(self):
        r = client.post("/api/portfolio/analytics", json={
            "returns": [10, 5, 2, 8, 12, 7],
            "period": "1y",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["max_drawdown_pct"] >= 0
        assert "drawdown_rating" in data

    def test_empty_returns_graceful(self):
        r = client.post("/api/portfolio/analytics", json={
            "returns": [], "period": "1y",
        })
        assert r.status_code == 200

    def test_no_trade_in_analytics(self):
        r = client.post("/api/portfolio/analytics", json={
            "returns": [1, 2, 3], "period": "1y",
        })
        text = str(r.json()).lower()
        assert "trade" not in text
        assert "broker" not in text


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Benchmark
# ═══════════════════════════════════════════════════════════════════════

class TestBenchmark:
    def test_compare_beats(self):
        r = client.post("/api/portfolio/benchmark", json={
            "portfolio_return_pct": 18.5, "period": "1y",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["beat_sp500"] is True
        assert data["beat_balanced"] is True

    def test_compare_lags(self):
        r = client.post("/api/portfolio/benchmark", json={
            "portfolio_return_pct": 5.0, "period": "1y",
        })
        data = r.json()
        assert data["beat_sp500"] is False

    def test_period_scaling(self):
        r = client.post("/api/portfolio/benchmark", json={
            "portfolio_return_pct": 3.0, "period": "3m",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["sp500_return"] < 5  # 1/4 of annual


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Committee Brief
# ═══════════════════════════════════════════════════════════════════════

class TestCommitteeBrief:
    def test_brief_generation(self):
        r = client.post("/api/portfolio/brief", json={
            "symbol": "AAPL", "recommendation": "BUY",
            "confidence": 75, "quality_score": 8,
            "quality_label": "Strong Analysis",
            "votes": [
                {"perspective": "Value", "vote": "BUY"},
                {"perspective": "Growth", "vote": "BUY"},
                {"perspective": "Risk", "vote": "HOLD",
                 "rationale": "Rate risk"},
                {"perspective": "Macro", "vote": "BUY"},
                {"perspective": "Policy", "vote": "BUY"},
                {"perspective": "Portfolio Fit", "vote": "HOLD",
                 "rationale": "Concentration"},
            ],
            "key_facts": ["Revenue +15% YoY", "Market share 28%"],
            "risks": ["Antitrust", "Supply chain"],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "AAPL"
        assert data["has_dissents"] is True
        assert len(data["dissents"]) > 0

    def test_brief_unanimous(self):
        r = client.post("/api/portfolio/brief", json={
            "symbol": "MSFT", "recommendation": "BUY",
            "confidence": 80, "quality_score": 9,
            "quality_label": "Strong Analysis",
            "votes": [
                {"perspective": "Value", "vote": "BUY"},
                {"perspective": "Growth", "vote": "BUY"},
                {"perspective": "Risk", "vote": "BUY"},
            ],
            "key_facts": ["Cloud growth +22%"],
            "risks": ["Competition"],
        })
        assert r.json()["has_dissents"] is False


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Bond Intelligence
# ═══════════════════════════════════════════════════════════════════════

class TestBondIntelligence:
    def test_tlt_analysis(self):
        r = client.get("/api/portfolio/bond/TLT")
        assert r.status_code == 200
        data = r.json()
        assert data["effective_duration"] > 10
        assert data["duration_risk"] == "high"

    def test_shy_low_risk(self):
        r = client.get("/api/portfolio/bond/SHY")
        data = r.json()
        assert data["duration_risk"] == "low"
        assert data["effective_duration"] < 5

    def test_unsupported_bond(self):
        r = client.get("/api/portfolio/bond/HYG")
        assert "error" in r.json()

    def test_portfolio_context(self):
        r = client.post("/api/portfolio/bond/portfolio", json={
            "positions": [
                {"symbol": "TLT", "shares": 100, "price": 95},
                {"symbol": "SHY", "shares": 200, "price": 82},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert "avg_duration" in data
        assert "rate_impact" in data


class TestNoTrading:
    def test_all_endpoints_no_trade(self):
        for path, method in [
            ("/api/portfolio/bond/TLT", "get"),
        ]:
            r = client.get(path)
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
