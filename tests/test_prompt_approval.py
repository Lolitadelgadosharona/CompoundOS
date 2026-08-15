"""M6-004 Slice B tests — prompt approval workflow (owner-gated)."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.prompt_governor import PromptGovernor

pytestmark = pytest.mark.postgres


def _draft_id(db_session, perspective):
    return db_session.execute(text(
        "SELECT id FROM prompt_templates"
        " WHERE perspective = :p AND status = 'draft'"
    ), {"p": perspective}).fetchone()[0]


class TestPromptApproval:
    def test_seed_as_draft(self, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        active = db_session.execute(text(
            "SELECT COUNT(*) FROM prompt_templates WHERE status = 'active'"
        )).scalar()
        assert active == 0

    def test_approve_draft_to_active(self, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        pid = _draft_id(db_session, "value")
        result = gov.approve(db_session, UUID(str(pid)))
        db_session.commit()
        assert result["status"] == "active"
        status = db_session.execute(text(
            "SELECT status FROM prompt_templates WHERE id = :id"
        ), {"id": pid}).scalar()
        assert status == "active"

    def test_approve_deprecates_previous_active(self, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        v1 = _draft_id(db_session, "value")
        gov.approve(db_session, UUID(str(v1)))
        db_session.commit()
        # insert a v2 draft for the same perspective
        v2 = uuid4()
        db_session.execute(text(
            "INSERT INTO prompt_templates (id, perspective, version, status,"
            " purpose, default_model, system_prompt, user_prompt_template,"
            " created_at)"
            " VALUES (:id, 'value', 2, 'draft', 'value', 'claude-sonnet-4',"
            " 's', 'u', NOW())"
        ), {"id": v2})
        db_session.commit()
        gov.approve(db_session, v2)
        db_session.commit()
        # v1 deprecated, v2 active → exactly one active
        active = db_session.execute(text(
            "SELECT COUNT(*) FROM prompt_templates"
            " WHERE perspective = 'value' AND status = 'active'"
        )).scalar()
        assert active == 1
        v1_status = db_session.execute(text(
            "SELECT status FROM prompt_templates WHERE id = :id"
        ), {"id": v1}).scalar()
        assert v1_status == "deprecated"

    def test_approve_deprecated_raises(self, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        pid = _draft_id(db_session, "value")
        gov.approve(db_session, UUID(str(pid)))
        db_session.commit()
        # deprecate it, then re-approve → error
        db_session.execute(text(
            "UPDATE prompt_templates SET status='deprecated' WHERE id=:id"
        ), {"id": pid})
        db_session.commit()
        with pytest.raises(ValueError):
            gov.approve(db_session, UUID(str(pid)))

    def test_approve_missing_raises(self, db_session):
        gov = PromptGovernor()
        with pytest.raises(ValueError):
            gov.approve(db_session, uuid4())


class TestPromptAPI:
    def test_list_endpoint(self, api_client, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        r = api_client.get("/api/prompts")
        assert r.status_code == 200
        assert len(r.json()["prompts"]) == 7

    def test_approve_endpoint(self, api_client, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        pid = _draft_id(db_session, "value")
        r = api_client.post(f"/api/prompts/{pid}/approve")
        assert r.status_code == 200
        assert r.json()["status"] == "active"
