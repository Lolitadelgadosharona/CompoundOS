"""M6-003 tests — execution reliability + cost trend."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services import observability_service

pytestmark = pytest.mark.postgres


def _seed(db_session, status="success", retry_count=0, duration_ms=100,
          cost=0.001, perspective="value", model="claude-sonnet-4",
          error=None):
    db_session.execute(text(
        "INSERT INTO llm_execution_log (id, perspective, model,"
        " input_tokens, output_tokens, cost_estimate, retry_count,"
        " status, duration_ms, error_message)"
        " VALUES (:id, :p, :m, 100, 50, :cost, :rc, :st, :dur, :err)"
    ), {"id": uuid4(), "p": perspective, "m": model, "cost": cost,
        "rc": retry_count, "st": status, "dur": duration_ms,
        "err": error})
    db_session.commit()


class TestExecutionReliability:
    def test_rates_and_latency(self, db_session):
        _seed(db_session, status="success", duration_ms=100)
        _seed(db_session, status="success", duration_ms=200)
        _seed(db_session, status="failure", duration_ms=50,
              retry_count=1, error="validation failed")
        _seed(db_session, status="timeout", duration_ms=300, retry_count=2)
        r = observability_service.execution_reliability(db_session)
        assert r["total_calls"] == 4
        assert r["success_rate"] == pytest.approx(0.5, abs=1e-3)
        assert r["failure_rate"] == pytest.approx(0.5, abs=1e-3)
        assert r["retry_rate"] == pytest.approx(0.5, abs=1e-3)
        assert r["avg_latency_ms"] == pytest.approx(162.5, abs=0.1)
        assert len(r["failure_by_perspective"]) >= 1
        assert len(r["recent_errors"]) == 1
        assert r["recent_errors"][0]["error_message"] == "validation failed"

    def test_by_status_breakdown(self, db_session):
        _seed(db_session, status="success")
        _seed(db_session, status="rate_limited", retry_count=3)
        r = observability_service.execution_reliability(db_session)
        statuses = {s["status"]: s["count"] for s in r["by_status"]}
        assert statuses["success"] == 1
        assert statuses["rate_limited"] == 1

    def test_empty_database(self, db_session):
        r = observability_service.execution_reliability(db_session)
        assert r["total_calls"] == 0
        assert r["success_rate"] == 0.0
        assert r["failure_rate"] == 0.0
        assert r["retry_rate"] == 0.0


class TestCostTrend:
    def test_daily_grouping(self, db_session):
        _seed(db_session, cost=0.001)
        _seed(db_session, cost=0.002, model="gpt-4o", perspective="growth")
        r = observability_service.cost_trend(db_session)
        assert r["days"] == 14
        assert len(r["daily"]) >= 1
        total_calls = sum(d["calls"] for d in r["daily"])
        assert total_calls == 2
        total_cost = sum(d["cost"] for d in r["daily"])
        assert total_cost == pytest.approx(0.003, abs=1e-6)

    def test_empty(self, db_session):
        r = observability_service.cost_trend(db_session)
        assert r["daily"] == []
        assert r["by_run"] == []
