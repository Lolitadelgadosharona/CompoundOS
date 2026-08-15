"""M6-003 tests — learning loop (outcome → accuracy → dashboard)."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services import dashboard_service
from apps.api.services.decision_lifecycle import LearningLoopService

pytestmark = pytest.mark.postgres


class TestLearningLoop:
    def test_record_outcome_writes_and_updates_accuracy(self, db_session):
        LearningLoopService.record_outcome(
            db_session, "AAPL", uuid4(), return_pct=5.0,
            perspective_scores={"value": 0.8, "growth": 0.6},
            predicted_confidence=70,
        )
        db_session.commit()

        outcome = db_session.execute(text(
            "SELECT past_outcomes FROM investment_knowledge_memory"
            " WHERE entity_key = 'AAPL' AND past_outcomes IS NOT NULL"
        )).fetchone()
        assert outcome is not None

        accuracy = db_session.execute(text(
            "SELECT prediction_accuracy FROM investment_knowledge_memory"
            " WHERE entity_key = 'AAPL' AND prediction_accuracy IS NOT NULL"
        )).fetchone()
        assert accuracy is not None

    def test_record_outcome_without_confidence_skips_accuracy(
            self, db_session):
        LearningLoopService.record_outcome(
            db_session, "MSFT", uuid4(), return_pct=3.0,
        )
        db_session.commit()
        accuracy = db_session.execute(text(
            "SELECT prediction_accuracy FROM investment_knowledge_memory"
            " WHERE entity_key = 'MSFT' AND prediction_accuracy IS NOT NULL"
        )).fetchone()
        assert accuracy is None

    def test_dashboard_reads_real_values(self, db_session):
        LearningLoopService.record_outcome(
            db_session, "AAPL", uuid4(), return_pct=5.0,
            perspective_scores={"value": 0.8, "growth": 0.6},
            predicted_confidence=70,
        )
        db_session.commit()

        metrics = dashboard_service.learning_metrics(db_session)
        by = {p["name"]: p for p in metrics["perspectives"]}
        assert by["Value"]["accuracy"] == pytest.approx(0.8, abs=1e-3)
        assert by["Growth"]["accuracy"] == pytest.approx(0.6, abs=1e-3)
        assert by["Value"]["samples"] == 1
        # error = 70 - int(5.0*10) = 20 → accuracy = 1 - 20/100 = 0.8
        assert metrics["accuracy"] == pytest.approx(0.8, abs=1e-2)
        assert len(metrics["outcomes"]) == 1
        assert metrics["outcomes"][0]["symbol"] == "AAPL"
        assert metrics["outcomes"][0]["return_pct"] == pytest.approx(5.0)

    def test_empty_database_safe(self, db_session):
        metrics = dashboard_service.learning_metrics(db_session)
        assert metrics["accuracy"] == 0.0
        assert metrics["perspectives"] == []
        assert metrics["outcomes"] == []
        assert metrics["review_count"] == 0


class TestLearningUI:
    def test_learning_page_renders(self, api_client):
        r = api_client.get("/learning")
        assert r.status_code == 200
        assert "Learning Dashboard" in r.text
        assert "Outcome History" in r.text

    def test_observability_page_renders_reliability(self, api_client):
        r = api_client.get("/observability")
        assert r.status_code == 200
        assert "Reliability" in r.text
        assert "Cost Trend" in r.text
