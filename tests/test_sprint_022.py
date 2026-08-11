"""Tests for Sprint 022 — Scale & Intelligence Enhancement."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    def test_add_node(self):
        r = client.post("/api/scale/graph/node", json={
            "node_id": "aapl", "node_type": "company",
            "label": "Apple Inc.",
        })
        assert r.status_code == 200
        assert r.json()["added"] == "aapl"

    def test_add_edge(self):
        client.post("/api/scale/graph/node", json={
            "node_id": "tech", "node_type": "sector",
            "label": "Technology",
        })
        r = client.post("/api/scale/graph/edge", json={
            "source_id": "aapl", "target_id": "tech",
            "edge_type": "BELONGS_TO",
        })
        assert r.status_code == 200

    def test_related(self):
        r = client.get("/api/scale/graph/related/aapl")
        assert r.status_code == 200
        data = r.json()
        assert len(data["related"]) >= 1

    def test_stats(self):
        r = client.get("/api/scale/graph/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["nodes"] >= 2


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Advanced AI Committee
# ═══════════════════════════════════════════════════════════════════════

class TestCommittee:
    def test_convene(self):
        r = client.post("/api/scale/committee/convene", json={
            "symbol": "AAPL",
            "votes": [
                {"perspective": "value", "vote": "BUY",
                 "confidence": 75, "rationale": "Undervalued"},
                {"perspective": "growth", "vote": "BUY",
                 "confidence": 70},
                {"perspective": "risk", "vote": "HOLD",
                 "confidence": 55},
                {"perspective": "macro", "vote": "HOLD",
                 "confidence": 50},
                {"perspective": "policy", "vote": "BUY",
                 "confidence": 80},
                {"perspective": "portfolio_fit", "vote": "BUY",
                 "confidence": 65},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["majority"] == "BUY"
        assert "claude" in data["by_model"]

    def test_divergence_detection(self):
        r = client.post("/api/scale/committee/convene", json={
            "symbol": "JNJ",
            "votes": [
                {"perspective": "value", "vote": "BUY",
                 "confidence": 85},
                {"perspective": "growth", "vote": "HOLD",
                 "confidence": 35},
            ],
        })
        data = r.json()
        assert data["divergence"] is True

    def test_no_forced_consensus(self):
        """Different models can disagree — committee preserves diversity."""
        r = client.post("/api/scale/committee/convene", json={
            "symbol": "MSFT",
            "votes": [
                {"perspective": "value", "vote": "BUY",
                 "confidence": 80},
                {"perspective": "risk", "vote": "HOLD",
                 "confidence": 30},
            ],
        })
        # Both perspectives are preserved, no consensus forced
        data = r.json()
        assert "by_model" in data


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Portfolio Monitoring
# ═══════════════════════════════════════════════════════════════════════

class TestMonitoring:
    def test_scan_positions(self):
        r = client.post("/api/scale/monitor/scan", json={
            "positions": [
                {"symbol": "AAPL", "daily_change_pct": 7.5,
                 "days_since_research": 15},
                {"symbol": "JNJ", "days_since_research": 120,
                 "days_to_earnings": 3},
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["alerts"]) >= 2

    def test_critical_price_shock(self):
        r = client.post("/api/scale/monitor/scan", json={
            "positions": [
                {"symbol": "TSLA", "daily_change_pct": -12},
            ],
        })
        alerts = r.json()["alerts"]
        assert alerts[0]["priority"] == "critical"

    def test_stale_research_flag(self):
        r = client.post("/api/scale/monitor/scan", json={
            "positions": [
                {"symbol": "PG", "days_since_research": 200},
            ],
        })
        alerts = r.json()["alerts"]
        has_stale = any(a["trigger"] == "research_stale"
                        for a in alerts)
        assert has_stale


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Family Office Layer
# ═══════════════════════════════════════════════════════════════════════

class TestFamilyOffice:
    def test_owner_full_access(self):
        r = client.post("/api/scale/office/auth", json={
            "user_id": "owner1", "role": "owner",
        })
        data = r.json()
        assert data["can_approve"] is True
        assert data["can_modify_policy"] is True

    def test_advisor_read_only(self):
        r = client.post("/api/scale/office/auth", json={
            "user_id": "advisor1", "role": "advisor",
        })
        data = r.json()
        assert data["can_approve"] is False
        assert data["can_modify_policy"] is False

    def test_consolidate(self):
        r = client.post("/api/scale/office/consolidate", json={
            "portfolios": [
                {"name": "Main", "type": "taxable",
                 "holdings": [
                     {"symbol": "AAPL", "shares": 100, "price": 175},
                 ]},
                {"name": "IRA", "type": "ira",
                 "holdings": [
                     {"symbol": "VOO", "shares": 50, "price": 450},
                 ]},
            ],
        })
        data = r.json()
        assert data["portfolio_count"] == 2
        assert data["total_value"] > 0


class TestNoTrading:
    def test_scale_endpoints_no_trade(self):
        for path in ["/api/scale/graph/stats",
                     "/api/scale/office/auth"]:
            r = client.get(path) if "stats" in path else client.post(
                path, json={"user_id": "x", "role": "owner"},
            )
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
