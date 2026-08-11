"""Tests for Sprint 017 — Intelligence Expansion."""

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.intelligence_expansion import (
    MacroService,
)

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Quality Scoring
# ═══════════════════════════════════════════════════════════════════════

class TestQualityScoring:
    def test_score_endpoint(self):
        r = client.post("/api/intel/quality/score", json={
            "memo": {
                "thesis": "Strong growth potential",
                "evidence": "Market share 28%",
                "bull_case": "AI monetization",
                "bear_case": "Regulatory risk",
                "risks": "Antitrust",
                "valuation": "DCF $195",
                "portfolio_impact": "Increases tech",
                "guardian_impact": "No violations",
                "committee": "6 votes",
                "decision_context": "Growth stage",
                "invalidation_conditions": "Competition",
            },
            "source_count": 3, "data_age_hours": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] >= 5
        assert data["label"] in (
            "Strong Analysis", "Adequate", "Needs Improvement",
        )

    def test_partial_memo_scores_lower(self):
        r = client.post("/api/intel/quality/score", json={
            "memo": {"thesis": "Buy"},
            "source_count": 0, "data_age_hours": 100,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] < 7

    def test_quality_is_informational_only(self):
        """Quality scores never gate memo access."""
        r = client.post("/api/intel/quality/score", json={
            "memo": {}, "source_count": 0, "data_age_hours": 0,
        })
        assert r.status_code == 200
        assert "label" in r.json()  # Returns score, never blocks


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Research Memory
# ═══════════════════════════════════════════════════════════════════════

class TestResearchMemory:
    def test_store_and_retrieve(self):
        r = client.post("/api/intel/memory/store", json={
            "symbol": "AAPL", "memo_id": "m1",
            "thesis": "Strong growth", "confidence": 75,
            "recommendation": "BUY", "tags": ["tech", "growth"],
        })
        assert r.status_code == 200

        r2 = client.get("/api/intel/memory/AAPL")
        assert r2.status_code == 200
        assert r2.json()["count"] >= 1

    def test_summary(self):
        client.post("/api/intel/memory/store", json={
            "symbol": "MSFT", "memo_id": "m2",
            "thesis": "Cloud growth", "confidence": 80,
            "recommendation": "BUY", "tags": ["tech"],
        })
        r = client.get("/api/intel/memory/MSFT/summary")
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_immutable_snapshots(self):
        """Stored entries persist; new entries don't overwrite."""
        client.post("/api/intel/memory/store", json={
            "symbol": "AAPL", "memo_id": "m3",
            "thesis": "First analysis", "confidence": 60,
            "recommendation": "HOLD",
        })
        client.post("/api/intel/memory/store", json={
            "symbol": "AAPL", "memo_id": "m4",
            "thesis": "Second analysis", "confidence": 80,
            "recommendation": "BUY",
        })
        r = client.get("/api/intel/memory/AAPL")
        assert r.status_code == 200
        # Both entries preserved
        assert r.json()["count"] >= 2

    def test_empty_symbol_returns_zero(self):
        r = client.get("/api/intel/memory/ZZZZ")
        assert r.status_code == 200
        assert r.json()["count"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Macro Intelligence
# ═══════════════════════════════════════════════════════════════════════

class TestMacro:
    def test_snapshot_endpoint(self):
        r = client.get("/api/intel/macro")
        assert r.status_code == 200
        data = r.json()
        assert "fed_funds_rate" in data
        assert "vix" in data
        assert "market_regime" in data
        assert "context_blurb" in data

    def test_context_is_factual(self):
        """Context blurb contains data, NOT recommendations."""
        r = client.get("/api/intel/macro")
        blurb = r.json()["context_blurb"]
        assert "buy" not in blurb.lower()
        assert "sell" not in blurb.lower()
        assert "should" not in blurb.lower()

    def test_recession_signal(self):
        snap = MacroService.snapshot()
        assert snap.recession_signal is True  # spread is -0.35

    def test_market_regime_bull(self):
        snap = MacroService.snapshot()
        assert snap.market_regime == "bull"  # S&P500 +12.5%


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Multi-Asset
# ═══════════════════════════════════════════════════════════════════════

class TestMultiAsset:
    def test_classify_stocks_and_etfs(self):
        r = client.post("/api/intel/multi-asset/classify", json={
            "holdings": [
                {"symbol": "AAPL", "asset_type": "stock",
                 "shares": 100, "price": 175},
                {"symbol": "VOO", "asset_type": "etf",
                 "shares": 50, "price": 450},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] > 0
        assert "stock" in data
        assert "etf" in data

    def test_unsupported_type_ignored(self):
        """Bonds not supported yet — they're skipped."""
        r = client.post("/api/intel/multi-asset/classify", json={
            "holdings": [
                {"symbol": "TLT", "asset_type": "bond",
                 "shares": 100, "price": 95},
                {"symbol": "AAPL", "asset_type": "stock",
                 "shares": 100, "price": 175},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert "bond" not in data  # Not in SUPPORTED set

    def test_etf_detail(self):
        r = client.get("/api/intel/multi-asset/etf/VOO")
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "etf"
        assert len(data["top_holdings"]) == 5


class TestNoTrading:
    def test_intel_endpoints_no_trade(self):
        for path in [
            "/api/intel/macro", "/api/intel/memory/AAPL",
        ]:
            r = client.get(path)
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
