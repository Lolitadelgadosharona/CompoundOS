"""Tests for Sprint 020 — Production Hardening."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Slice C — AI Quality Calibration
# ═══════════════════════════════════════════════════════════════════════

class TestCalibration:
    def test_consistent_scores(self):
        r = client.post("/api/hardening/ai/calibrate", json={
            "symbol": "AAPL", "confidence_scores": [72, 74, 70, 73, 71],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_consistent"] is True
        assert data["std_deviation"] < 10

    def test_inconsistent_scores(self):
        r = client.post("/api/hardening/ai/calibrate", json={
            "symbol": "JNJ",
            "confidence_scores": [80, 45, 75, 30, 90],
        })
        data = r.json()
        assert data["is_consistent"] is False
        assert data["std_deviation"] > 10

    def test_verify_claims_all_backed(self):
        r = client.post("/api/hardening/ai/verify", json={
            "claims": [
                {"claim": "Revenue +15%", "evidence_source": "Alpha Vantage"},
                {"claim": "Market share 28%", "evidence_source": "SEC filing"},
            ],
        })
        data = r.json()
        assert data["summary"]["unverified"] == 0

    def test_verify_unverified_claims(self):
        r = client.post("/api/hardening/ai/verify", json={
            "claims": [
                {"claim": "Stock will double next year",
                 "evidence_source": ""},
            ],
        })
        data = r.json()
        assert data["summary"]["unverified"] == 1
        assert data["summary"]["quality_penalty"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Data Reliability
# ═══════════════════════════════════════════════════════════════════════

class TestReliability:
    def test_provider_health(self):
        r = client.get("/api/hardening/reliability/health")
        assert r.status_code == 200
        data = r.json()
        assert len(data["providers"]) == 4
        assert data["all_healthy"] is True

    def test_pipeline_health(self):
        r = client.get("/api/hardening/reliability/pipeline")
        assert r.status_code == 200
        data = r.json()
        assert "all_healthy" in data

    def test_cache_fresh(self):
        r = client.post("/api/hardening/reliability/cache", json={
            "cached_age_hours": 2, "max_age_hours": 6,
        })
        data = r.json()
        assert data["status"] == "fresh"
        assert data["should_refetch"] is False

    def test_cache_stale(self):
        r = client.post("/api/hardening/reliability/cache", json={
            "cached_age_hours": 48, "max_age_hours": 6,
        })
        data = r.json()
        assert data["should_refetch"] is True


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Security
# ═══════════════════════════════════════════════════════════════════════

class TestSecurity:
    def test_audit_endpoint(self):
        r = client.get("/api/hardening/security/audit")
        assert r.status_code == 200
        data = r.json()
        assert len(data["findings"]) == 7
        assert data["summary"]["pass"] >= 4

    def test_audit_has_recommendations(self):
        r = client.get("/api/hardening/security/audit")
        findings = r.json()["findings"]
        for f in findings:
            assert "recommendation" in f
            assert "status" in f

    def test_no_secrets_in_response(self):
        r = client.get("/api/hardening/security/audit")
        text = str(r.json()).lower()
        assert "password" not in text
        assert "secret" not in text
        assert "key=" not in text


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Owner Experience
# ═══════════════════════════════════════════════════════════════════════

class TestUX:
    def test_ux_settings(self):
        r = client.get("/api/hardening/ux/settings")
        assert r.status_code == 200
        data = r.json()
        assert "theme" in data
        assert len(data["shortcuts"]) >= 2

    def test_loading_states(self):
        r = client.get("/api/hardening/ux/loading-states")
        assert r.status_code == 200
        data = r.json()
        assert "error_display" in data

    def test_accessibility(self):
        r = client.get("/api/hardening/ux/accessibility")
        assert r.status_code == 200
        data = r.json()
        assert "contrast" in data


class TestNoTrading:
    def test_no_trade_in_hardening(self):
        for path in ["/api/hardening/security/audit",
                     "/api/hardening/ux/settings"]:
            r = client.get(path)
            text = str(r.json()).lower()
            assert "trade" not in text
            assert "broker" not in text
