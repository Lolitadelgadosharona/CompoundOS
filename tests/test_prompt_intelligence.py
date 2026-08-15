"""M6-004 Slice C tests — prompt version analytics (read-only)."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services import observability_service
from apps.api.services.prompt_governor import PromptGovernor

pytestmark = pytest.mark.postgres


def _seed_and_approve(db_session):
    gov = PromptGovernor()
    gov.seed_defaults(db_session)
    db_session.commit()
    for p in gov.list_prompts(db_session):
        if p["status"] == "draft":
            gov.approve(db_session, UUID(p["id"]))
    db_session.commit()
    return gov


class TestPromptIntelligence:
    def test_prompt_version_stats_aggregates(self, db_session):
        _seed_and_approve(db_session)
        pid = db_session.execute(text(
            "SELECT id FROM prompt_templates WHERE perspective = 'value'"
        )).fetchone()[0]
        db_session.execute(text(
            "INSERT INTO llm_execution_log (id, prompt_template_id,"
            " perspective, status, duration_ms, cost_estimate,"
            " input_tokens, output_tokens)"
            " VALUES (:id, :ptid, 'value', 'success', 100, 0.001, 100, 50)"
        ), {"id": uuid4(), "ptid": pid})
        db_session.commit()

        stats = observability_service.prompt_version_stats(db_session)
        value = [s for s in stats if s["perspective"] == "value"][0]
        assert value["executions"] == 1
        assert value["success"] == 1
        assert value["failure"] == 0
        assert value["success_rate"] == 1.0
        assert value["cost"] == pytest.approx(0.001, abs=1e-6)

    def test_prompt_version_stats_empty_executions(self, db_session):
        _seed_and_approve(db_session)
        stats = observability_service.prompt_version_stats(db_session)
        assert len(stats) == 7
        for s in stats:
            assert s["executions"] == 0
            assert s["success_rate"] == 0.0

    def test_prompt_version_stats_empty_database(self, db_session):
        stats = observability_service.prompt_version_stats(db_session)
        assert stats == []


class TestPromptIntelligenceUI:
    def test_observability_page_renders_prompt_versions(self, api_client):
        r = api_client.get("/observability")
        assert r.status_code == 200
        assert "Prompt Versions" in r.text
