"""PE-002 tests — Ask CIO Flow (symbol resolver + endpoint + UI)."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.dashboard_research import DashboardResearchService
from apps.api.services.symbol_resolver import (
    SymbolResolutionError,
    resolve_symbol,
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
    return db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()[0]


class TestSymbolResolver:
    def test_explicit_dollar_ticker(self):
        assert resolve_symbol("Should I buy $NVDA?") == "NVDA"

    def test_bare_ticker(self):
        assert resolve_symbol("NVDA position size?") == "NVDA"

    def test_company_name(self):
        assert resolve_symbol("Should I increase Nvidia position?") == "NVDA"
        assert resolve_symbol("What about Apple?") == "AAPL"
        assert resolve_symbol("Microsoft valuation?") == "MSFT"

    def test_all_supported_companies(self):
        cases = {
            "Nvidia": "NVDA", "Apple": "AAPL", "Microsoft": "MSFT",
            "Tesla": "TSLA", "Amazon": "AMZN", "Google": "GOOGL",
            "Meta": "META",
        }
        for name, ticker in cases.items():
            assert resolve_symbol(f"Should I buy {name}?") == ticker

    def test_unknown_input_raises(self):
        with pytest.raises(SymbolResolutionError):
            resolve_symbol("What is the meaning of life?")
        with pytest.raises(SymbolResolutionError):
            resolve_symbol("")

    def test_deterministic_no_ai(self):
        # same input → same output (pure function)
        assert resolve_symbol("Nvidia") == resolve_symbol("Nvidia")


class TestAskCioEndpoint:
    def test_ask_returns_run_id(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/cio/ask",
                            json={"question": "Should I buy Nvidia?"})
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "NVDA"
        assert "run_id" in data
        assert data["status"] == "pending"

    def test_ask_unknown_symbol_400(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/cio/ask",
                            json={"question": "asdf qwerty zxcv"})
        assert r.status_code == 400

    def test_ask_no_household_404(self, api_client):
        r = api_client.post("/api/cio/ask",
                            json={"question": "Should I buy Nvidia?"})
        assert r.status_code == 404


class TestQuestionSaved:
    def test_question_saved_to_parameters(self, db_session):
        hh = _setup_household(db_session)
        result = DashboardResearchService.create_request(
            db_session, "NVDA", hh, title="Should I buy Nvidia?",
        )
        row = db_session.execute(text(
            "SELECT parameters FROM research_requests WHERE id = :id"
        ), {"id": UUID(result["request_id"])}).fetchone()
        assert row[0]["question"] == "Should I buy Nvidia?"
        assert row[0]["symbol"] == "NVDA"

    def test_default_title_backward_compatible(self, db_session):
        hh = _setup_household(db_session)
        result = DashboardResearchService.create_request(
            db_session, "AAPL", hh,
        )
        row = db_session.execute(text(
            "SELECT parameters FROM research_requests WHERE id = :id"
        ), {"id": UUID(result["request_id"])}).fetchone()
        assert row[0] is None  # no title → no parameters


class TestDecisionIdInStatus:
    def test_status_includes_decision_id(self, api_client):
        from apps.api.services.pipeline_async import (
            PipelineProgressTracker,
            PipelineState,
        )
        rid = uuid4()
        PipelineProgressTracker.create(rid)
        PipelineProgressTracker.update(
            rid, PipelineState.COMPLETE,
            memo_id="memo-123", decision_id="decision-456",
        )
        r = api_client.get(f"/api/research/{rid}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["memo_id"] == "memo-123"
        assert data["decision_id"] == "decision-456"
        assert data["is_complete"] is True


class TestAskCioAsync:
    def test_ask_returns_immediately(self, api_client, db_session, monkeypatch):
        """POST /api/cio/ask returns 'pending' — it never awaits the pipeline."""
        _setup_household(db_session)
        from apps.api.routers import cio

        calls = []

        def slow_pipeline(*args, **kwargs):
            calls.append(args)

        monkeypatch.setattr(cio, "execute_pipeline", slow_pipeline)
        r = api_client.post("/api/cio/ask",
                            json={"question": "Should I buy Nvidia?"})
        assert r.status_code == 200
        body = r.json()
        # "pending" (not "completed") proves the endpoint returned before
        # the pipeline ran — the pipeline is scheduled in the background.
        assert body["status"] == "pending"
        assert body["symbol"] == "NVDA"
        assert len(calls) == 1

    def test_execute_pipeline_is_sync_not_async(self):
        """The pipeline must be a sync callable so BackgroundTasks runs it
        in a threadpool (never blocking the event loop)."""
        import inspect

        from apps.api.services.pipeline_async import execute_pipeline

        assert not inspect.iscoroutinefunction(execute_pipeline)

    def test_background_execution_updates_tracker(
        self, api_client, db_session, monkeypatch,
    ):
        """The background task drives the tracker to completion."""
        _setup_household(db_session)
        from apps.api.routers import cio
        from apps.api.services.pipeline_async import (
            PipelineProgressTracker,
            PipelineState,
        )

        def fake_pipeline(run_id, symbol, household_id):
            PipelineProgressTracker.update(
                run_id, PipelineState.COMPLETE,
                memo_id="memo-x", decision_id="decision-y",
            )

        monkeypatch.setattr(cio, "execute_pipeline", fake_pipeline)
        r = api_client.post("/api/cio/ask",
                            json={"question": "Should I buy Nvidia?"})
        run_id = r.json()["run_id"]
        s = api_client.get(f"/api/research/{run_id}/status")
        data = s.json()
        assert data["is_complete"] is True
        assert data["memo_id"] == "memo-x"
        assert data["decision_id"] == "decision-y"


class TestResearchPage:
    def test_ask_cio_ui_renders(self, api_client):
        r = api_client.get("/research")
        assert r.status_code == 200
        assert "Ask CIO" in r.text
        assert "cio-question" in r.text

    def test_research_page_has_polling_js(self, api_client):
        """The page polls the status endpoint (async job, no blocking)."""
        r = api_client.get("/research")
        assert r.status_code == 200
        assert "pollCio" in r.text
        assert "fetch('/api/research/'" in r.text
        assert "setTimeout(r, 2000)" in r.text

    def test_no_ai_calls(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/research")
        assert r.status_code == 200
        count = db_session.execute(text(
            "SELECT COUNT(*) FROM llm_execution_log"
        )).scalar()
        assert count == 0

    def test_no_secrets(self, api_client):
        r = api_client.get("/research")
        assert r.status_code == 200
        lower = r.text.lower()
        for secret in ("password", "gho_", "sk-ss-v1", "x-api-key"):
            assert secret not in lower
