"""M6-001 tests — observability service, API, provider + AI health."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services import observability_service
from apps.api.services.health_service import (
    DEGRADED,
    HEALTHY,
    UNKNOWN,
    check_ai_execution,
    check_providers,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


def _seed_execution(db_session, perspective="value",
                    model="claude-sonnet-4",
                    input_tokens: Optional[int] = 100,
                    output_tokens: Optional[int] = 50,
                    cost: Optional[float] = 0.0015,
                    status="success", run_id=None):
    db_session.execute(text(
        "INSERT INTO llm_execution_log (id, run_id, perspective, model,"
        " input_tokens, output_tokens, cost_estimate, cost_currency,"
        " retry_count, status, duration_ms)"
        " VALUES (:id, :rid, :p, :m, :it, :ot, :cost, 'USD', 0, :st, 100)"
    ), {"id": uuid4(), "rid": run_id, "p": perspective, "m": model,
        "it": input_tokens, "ot": output_tokens, "cost": cost,
        "st": status})
    db_session.commit()


def _setup_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement,"
        " notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        " ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()
    return db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()[0]


def _setup_run(db_session, household_id):
    """Minimal idea → review → request → run FK chain; returns run_id."""
    idea_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title, status,"
        " source, confidence, created_at)"
        " VALUES (:id, :hh, 'AAPL', 'draft', 'owner', 'LOW', NOW())"
    ), {"id": idea_id, "hh": household_id})
    rr_id = uuid4()
    db_session.execute(text(
        "INSERT INTO committee_review_requests (id, investment_idea_id,"
        " status, requested_by, created_at)"
        " VALUES (:id, :iid, 'pending', 'owner', NOW())"
    ), {"id": rr_id, "iid": idea_id})
    req_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_requests (id, review_request_id, status,"
        " created_at, updated_at)"
        " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
    ), {"id": req_id, "rrid": rr_id})
    run_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number, status,"
        " created_at, updated_at)"
        " VALUES (:id, :req, 1, 'completed', NOW(), NOW())"
    ), {"id": run_id, "req": req_id})
    db_session.commit()
    return run_id


# ── Observability service ────────────────────────────────────────────────


class TestObservabilityService:
    def test_execution_summary(self, db_session):
        _seed_execution(db_session, "value", cost=0.003, input_tokens=1000,
                        output_tokens=100)
        _seed_execution(db_session, "growth", model="gpt-4o", cost=0.001,
                        input_tokens=200, output_tokens=100)
        _seed_execution(db_session, "risk", status="failure", cost=0.0,
                        input_tokens=0, output_tokens=0)
        s = observability_service.execution_summary(db_session)
        assert s["total_calls"] == 3
        assert s["success"] == 2
        assert s["failure"] == 1
        assert s["total_input_tokens"] == 1200
        assert s["total_output_tokens"] == 200
        assert s["total_cost"] == pytest.approx(0.004, abs=1e-6)

    def test_cost_by_perspective(self, db_session):
        _seed_execution(db_session, "value", cost=0.003)
        _seed_execution(db_session, "value", cost=0.002)
        _seed_execution(db_session, "macro", cost=0.001)
        rows = observability_service.cost_by_perspective(db_session)
        by = {r["perspective"]: r for r in rows}
        assert by["value"]["calls"] == 2
        assert by["value"]["total_cost"] == pytest.approx(0.005, abs=1e-6)
        assert by["macro"]["calls"] == 1

    def test_list_executions(self, db_session):
        _seed_execution(db_session, "value")
        _seed_execution(db_session, "growth", model="gpt-4o")
        rows = observability_service.list_executions(db_session)
        assert len(rows) == 2
        assert rows[0]["model"] in ("claude-sonnet-4", "gpt-4o")

    def test_null_safety(self, db_session):
        _seed_execution(db_session, "value", input_tokens=None,
                        output_tokens=None, cost=None)
        s = observability_service.execution_summary(db_session)
        assert s["total_input_tokens"] == 0
        assert s["total_output_tokens"] == 0
        assert s["total_cost"] == 0.0

    def test_cost_by_run(self, db_session):
        hh = _setup_household(db_session)
        run_a = _setup_run(db_session, hh)
        _seed_execution(db_session, "value", cost=0.002, run_id=run_a)
        _seed_execution(db_session, "growth", cost=0.001, run_id=run_a)
        rows = observability_service.cost_by_run(db_session)
        assert len(rows) == 1
        assert rows[0]["run_id"] == str(run_a)
        assert rows[0]["calls"] == 2
        assert rows[0]["total_cost"] == pytest.approx(0.003, abs=1e-6)


# ── Observability API ────────────────────────────────────────────────────


class TestObservabilityAPI:
    def test_executions_endpoint(self, api_client, db_session):
        _seed_execution(db_session, "value")
        r = api_client.get("/api/observability/executions")
        assert r.status_code == 200
        assert "executions" in r.json()

    def test_cost_endpoint(self, api_client, db_session):
        _seed_execution(db_session, "value", cost=0.003)
        r = api_client.get("/api/observability/cost")
        assert r.status_code == 200
        body = r.json()
        assert "total_cost" in body
        assert "by_perspective" in body
        assert "by_run" in body

    def test_summary_endpoint(self, api_client, db_session):
        _seed_execution(db_session, "value")
        r = api_client.get("/api/observability/summary")
        assert r.status_code == 200
        assert r.json()["total_calls"] == 1

    def test_empty_database(self, api_client):
        r = api_client.get("/api/observability/summary")
        assert r.status_code == 200
        assert r.json()["total_calls"] == 0


# ── Provider health ──────────────────────────────────────────────────────


class TestProviderHealth:
    def test_all_missing(self, monkeypatch):
        for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                    "OPENAI_API_KEY", "AV_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        h = check_providers(_now())
        assert h.status == DEGRADED
        assert "Missing credentials" in h.reason

    def test_all_configured(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AV_API_KEY", "test-key")
        h = check_providers(_now())
        assert h.status == HEALTHY
        assert h.details["anthropic"] == "configured"
        assert h.details["openai"] == "configured"
        assert h.details["alpha_vantage"] == "configured"


# ── AI execution health ──────────────────────────────────────────────────


class TestAIExecutionHealth:
    def test_no_executions(self, db_session):
        h = check_ai_execution(db_session, _now())
        assert h.status == UNKNOWN

    def test_healthy(self, db_session):
        _seed_execution(db_session, "value", status="success")
        _seed_execution(db_session, "growth", status="success")
        h = check_ai_execution(db_session, _now())
        assert h.status == HEALTHY
        assert h.details["failures_24h"] == 0

    def test_degraded_on_majority_failure(self, db_session):
        _seed_execution(db_session, "value", status="success")
        _seed_execution(db_session, "growth", status="failure")
        _seed_execution(db_session, "risk", status="timeout")
        h = check_ai_execution(db_session, _now())
        assert h.status == DEGRADED
        assert h.details["failures_24h"] == 2

    def test_healthy_on_transient_failure(self, db_session):
        _seed_execution(db_session, "value", status="success")
        _seed_execution(db_session, "growth", status="success")
        _seed_execution(db_session, "risk", status="success")
        _seed_execution(db_session, "macro", status="failure")
        h = check_ai_execution(db_session, _now())
        assert h.status == HEALTHY
        assert h.details["failures_24h"] == 1
