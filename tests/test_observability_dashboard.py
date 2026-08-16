"""M6-002 tests — observability page + dashboard health card rendering."""

from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


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


# ── Observability page ────────────────────────────────────────────────────


class TestObservabilityPage:
    def test_page_renders(self, api_client):
        r = api_client.get("/observability")
        assert r.status_code == 200
        assert "AI Execution Summary" in r.text
        assert "Provider Status" in r.text
        assert "AI Execution Health" in r.text

    def test_empty_database(self, api_client):
        r = api_client.get("/observability")
        assert r.status_code == 200
        assert "No executions recorded" in r.text

    def test_seeded_display(self, api_client, db_session):
        _seed_execution(db_session, "value", cost=0.003,
                        input_tokens=1000, output_tokens=100)
        _seed_execution(db_session, "growth", model="gpt-4o", cost=0.001)
        r = api_client.get("/observability")
        assert r.status_code == 200
        body = r.text
        assert "AI Execution Summary" in body
        # total estimated cost = 0.003 + 0.001 = 0.004
        assert "0.0040" in body
        # per-perspective values
        assert "0.0030" in body
        assert "value" in body
        assert "growth" in body

    def test_provider_status_renders(self, api_client):
        r = api_client.get("/observability")
        assert r.status_code == 200
        assert "Anthropic" in r.text
        assert "OpenAI" in r.text
        assert "AlphaVantage" in r.text


# ── Dashboard health card ─────────────────────────────────────────────────


class TestDashboardHealthCard:
    def test_health_card_renders(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/dashboard")
        assert r.status_code == 200
        assert "AI System" in r.text
