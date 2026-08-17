"""PE-002.2a tests — CIO Query Understanding Layer."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.cio_query import (
    CIOQueryError,
    QueryIntent,
    QueryRoute,
    understand_query,
)

pytestmark = pytest.mark.postgres


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
    return hh


class TestDeterministicResolution:
    def test_nvidia_company(self, db_session):
        _setup_household(db_session)
        q = understand_query(db_session, "Should I buy Nvidia?")
        assert q.intent == QueryIntent.COMPANY
        assert q.symbol == "NVDA"
        assert q.route == QueryRoute.RESEARCH
        assert q.confidence.value == "high"

    def test_microsoft_company(self, db_session):
        _setup_household(db_session)
        q = understand_query(db_session, "Microsoft future?")
        assert q.intent == QueryIntent.COMPANY
        assert q.symbol == "MSFT"

    def test_qqq_etf(self, db_session):
        _setup_household(db_session)
        q = understand_query(db_session, "QQQ investment?")
        assert q.intent == QueryIntent.ETF
        assert q.symbol == "QQQ"
        assert q.route == QueryRoute.RESEARCH

    def test_spy_etf(self, db_session):
        _setup_household(db_session)
        q = understand_query(db_session, "Should I buy $SPY?")
        assert q.intent == QueryIntent.ETF
        assert q.symbol == "SPY"

    def test_portfolio_intent(self, db_session):
        _setup_household(db_session)
        q = understand_query(db_session, "How risky is my portfolio?")
        assert q.intent == QueryIntent.PORTFOLIO
        assert q.route == QueryRoute.PORTFOLIO
        assert q.symbol is None


class TestGracefulFailure:
    def test_unknown_input_fails_closed(self, db_session):
        _setup_household(db_session)
        with pytest.raises(CIOQueryError):
            understand_query(db_session, "asdf qwerty zxcv")

    def test_empty_question(self, db_session):
        _setup_household(db_session)
        with pytest.raises(CIOQueryError):
            understand_query(db_session, "")


class TestRouter:
    def test_ask_unknown_returns_400(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/cio/ask",
                            json={"question": "asdf qwerty zxcv"})
        assert r.status_code == 400

    def test_ask_portfolio_route(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/cio/ask",
                            json={"question": "How risky is my portfolio?"})
        assert r.status_code == 200
        body = r.json()
        assert body["route"] == "portfolio"

    def test_ask_research_route(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/cio/ask",
                            json={"question": "Should I buy Nvidia?"})
        assert r.status_code == 200
        body = r.json()
        assert body["route"] == "research"
        assert body["symbol"] == "NVDA"
        assert "run_id" in body
