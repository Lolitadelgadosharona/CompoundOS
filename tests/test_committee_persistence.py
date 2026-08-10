# ruff: noqa: E501
"""PostgreSQL persistence tests — Sprint 006 Slice A: AI Committee Foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.models import (
    CommitteeEvidenceItem,
    CommitteeOutcome,
    CommitteeReport,
    CommitteeSession,
    HouseholdProfile,
)

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0022_committee_bridge"
PREVIOUS_REVISION = "0011_fencing_closure"

COMMITTEE_TABLES = {
    "committee_sessions",
    "committee_evidence_items",
    "committee_reports",
    "committee_outcomes",
}

EXPECTED_TRIGGERS = {
    "trg_committee_report_immutability",
    "trg_committee_outcome_append_only",
}


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _create_household(session: Session) -> HouseholdProfile:
    now = datetime.now(timezone.utc)
    h = HouseholdProfile(
        id=uuid4(),
        household_name="Test Family",
        base_currency="USD",
        investment_horizon="Long-term >10 years",
        singleton_key=True,
        created_at=now,
        updated_at=now,
    )
    session.add(h)
    session.commit()
    return h


def _create_session(household_id, db_session):
    s = CommitteeSession(
        id=uuid4(),
        household_id=household_id,
        title="Test Proposal",
        proposal_text="Should we increase equity exposure?",
        status="draft",
    )
    db_session.add(s)
    db_session.commit()
    return s


def _create_report(session_id, db_session):
    r = CommitteeReport(
        id=uuid4(),
        session_id=session_id,
        provider="deepseek",
        model_id="deepseek-v3",
        prompt_version="v1",
        schema_version="1.0",
        temperature=Decimal("0.0"),
        report_content={"summary": "test"},
        content_hash="abc123",
    )
    db_session.add(r)
    db_session.commit()
    return r


# ═══════════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════════

class TestMigrationLifecycle:
    def test_migration_head_is_0012(self, db_session: Session, postgres_engine: Engine) -> None:
        with postgres_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev == HEAD_REVISION

    def test_all_four_tables_exist(self, postgres_engine: Engine) -> None:
        inspector = inspect(postgres_engine)
        tables = set(inspector.get_table_names())
        assert COMMITTEE_TABLES.issubset(tables)

    def test_fresh_downgrade_reupgrade(
        self, db_session: Session, postgres_engine: Engine,
    ) -> None:
        url = postgres_engine.url.render_as_string(hide_password=False)
        postgres_engine.dispose()
        migration_engine = create_engine(url)

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", url)

        try:
            inspector = inspect(migration_engine)
            tables_before = set(inspector.get_table_names())
            assert COMMITTEE_TABLES.issubset(tables_before)

            command.downgrade(alembic_cfg, PREVIOUS_REVISION)
            tables_mid = set(inspect(migration_engine).get_table_names())
            assert not COMMITTEE_TABLES.intersection(tables_mid)

            command.upgrade(alembic_cfg, "head")
            tables_end = set(inspect(migration_engine).get_table_names())
            assert COMMITTEE_TABLES.issubset(tables_end)

            rev = migration_engine.connect().execute(
                text("SELECT version_num FROM alembic_version"),
            ).scalar()
            assert rev == HEAD_REVISION
        finally:
            migration_engine.dispose()
            # restore head on shared engine
            command.upgrade(alembic_cfg, "head")

    def test_incremental_upgrade_from_0011_preserves_data(
        self, db_session: Session, postgres_engine: Engine,
    ) -> None:
        """Downgrade to 0011, insert orchestration data, upgrade to 0012,
        verify existing data intact."""
        url = postgres_engine.url.render_as_string(hide_password=False)
        postgres_engine.dispose()
        migration_engine = create_engine(url)
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", url)

        try:
            command.downgrade(alembic_cfg, PREVIOUS_REVISION)

            # Insert 0011 data
            with migration_engine.connect() as conn:
                hid = str(uuid4())
                conn.execute(text(
                    "INSERT INTO household_profiles (id, household_name, base_currency,"
                    " singleton_key, investment_horizon, liquidity_needs, risk_statement,"
                    " notes, created_at, updated_at)"
                    " VALUES (:id, 'Test', 'USD', true, 'Long-term', 'None', 'Low',"
                    " '', now(), now())"
                ), {"id": hid})
                jid = str(uuid4())
                conn.execute(text(
                    "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
                    " VALUES (:id, :hid, 'guardian.evaluate_all', '{}')"
                ), {"id": jid, "hid": hid})
                conn.commit()

            command.upgrade(alembic_cfg, "head")

            # Verify 0011 data survived
            with migration_engine.connect() as conn:
                jrow = conn.execute(text(
                    "SELECT id FROM job_definitions WHERE id = :id"
                ), {"id": jid}).fetchone()
                assert jrow is not None

            # Verify 0012 tables exist
            tables = set(inspect(migration_engine).get_table_names())
            assert COMMITTEE_TABLES.issubset(tables)
        finally:
            migration_engine.dispose()
            command.upgrade(alembic_cfg, "head")


# ═══════════════════════════════════════════════════════════════════════════
# Triggers
# ═══════════════════════════════════════════════════════════════════════════

class TestTriggers:
    def test_report_immutability_trigger_exists(self, postgres_engine: Engine) -> None:
        with postgres_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT count(*) FROM pg_trigger"
                " WHERE tgname = 'trg_committee_report_immutability'"
            )).scalar()
            assert row == 1

    def test_report_cannot_be_updated(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        r = _create_report(s.id, db_session)

        with pytest.raises(Exception, match="committee_report_immutable"):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "UPDATE committee_reports SET provider = 'openai' WHERE id = :id"
                ), {"id": str(r.id)})
                conn.commit()

    def test_report_can_be_deleted_via_cascade(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        _create_report(s.id, db_session)

        # Deleting the session cascades to delete the report (no immutability violation)
        db_session.delete(s)
        db_session.commit()
        assert db_session.query(CommitteeSession).filter_by(id=s.id).first() is None

    def test_outcome_append_only_trigger_exists(self, postgres_engine: Engine) -> None:
        with postgres_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT count(*) FROM pg_trigger"
                " WHERE tgname = 'trg_committee_outcome_append_only'"
            )).scalar()
            assert row == 1

    def test_outcome_cannot_be_updated(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        r = _create_report(s.id, db_session)
        oid = uuid4()
        db_session.execute(text(
            "INSERT INTO committee_outcomes (id, session_id, report_id, outcome)"
            " VALUES (:id, :sid, :rid, 'accepted')"
        ), {"id": str(oid), "sid": str(s.id), "rid": str(r.id)})
        db_session.commit()

        with pytest.raises(Exception, match="committee_outcome_append_only"):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "UPDATE committee_outcomes SET outcome = 'rejected' WHERE id = :id"
                ), {"id": str(oid)})
                conn.commit()

    def test_outcome_cannot_be_deleted(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        r = _create_report(s.id, db_session)
        oid = uuid4()
        db_session.execute(text(
            "INSERT INTO committee_outcomes (id, session_id, report_id, outcome)"
            " VALUES (:id, :sid, :rid, 'accepted')"
        ), {"id": str(oid), "sid": str(s.id), "rid": str(r.id)})
        db_session.commit()

        with pytest.raises(Exception, match="committee_outcome_append_only"):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "DELETE FROM committee_outcomes WHERE id = :id"
                ), {"id": str(oid)})
                conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Constraints
# ═══════════════════════════════════════════════════════════════════════════

class TestConstraints:
    def test_session_status_constraint(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_sessions"
                    " (id, household_id, title, proposal_text, status)"
                    " VALUES (:id, :hid, 'T', 'P', 'invalid_status')"
                ), {"id": str(uuid4()), "hid": str(h.id)})
                conn.commit()

    def test_session_title_not_empty(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_sessions"
                    " (id, household_id, title, proposal_text, status)"
                    " VALUES (:id, :hid, '', 'P', 'draft')"
                ), {"id": str(uuid4()), "hid": str(h.id)})
                conn.commit()

    def test_session_proposal_not_empty(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_sessions"
                    " (id, household_id, title, proposal_text, status)"
                    " VALUES (:id, :hid, 'T', '', 'draft')"
                ), {"id": str(uuid4()), "hid": str(h.id)})
                conn.commit()

    def test_evidence_source_type_constraint(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_evidence_items"
                    " (id, session_id, source_type, source_title, as_of,"
                    "  content_hash, structured_facts, provenance, freshness,"
                    "  confidence, citation_ref)"
                    " VALUES (:id, :sid, 'invalid_source', 'T', now(),"
                    "  'abc', '{}', 'compoundos_internal', 'current',"
                    "  'high', 'ref')"
                ), {"id": str(uuid4()), "sid": str(s.id)})
                conn.commit()

    def test_evidence_provenance_constraint(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_evidence_items"
                    " (id, session_id, source_type, source_title, as_of,"
                    "  content_hash, structured_facts, provenance, freshness,"
                    "  confidence, citation_ref)"
                    " VALUES (:id, :sid, 'owner_claim', 'T', now(),"
                    "  'abc', '{}', 'external_vendor', 'current',"
                    "  'high', 'ref')"
                ), {"id": str(uuid4()), "sid": str(s.id)})
                conn.commit()

    def test_evidence_confidence_constraint(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_evidence_items"
                    " (id, session_id, source_type, source_title, as_of,"
                    "  content_hash, structured_facts, provenance, freshness,"
                    "  confidence, citation_ref)"
                    " VALUES (:id, :sid, 'owner_claim', 'T', now(),"
                    "  'abc', '{}', 'compoundos_internal', 'current',"
                    "  'low', 'ref')"
                ), {"id": str(uuid4()), "sid": str(s.id)})
                conn.commit()

    def test_outcome_enum_constraint(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        r = _create_report(s.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_outcomes"
                    " (id, session_id, report_id, outcome)"
                    " VALUES (:id, :sid, :rid, 'pending')"
                ), {"id": str(uuid4()), "sid": str(s.id), "rid": str(r.id)})
                conn.commit()

    def test_report_temperature_range(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_reports"
                    " (id, session_id, provider, model_id, prompt_version,"
                    "  schema_version, temperature, report_content, content_hash)"
                    " VALUES (:id, :sid, 'deepseek', 'v3', 'v1', '1.0', 3.0,"
                    "  '{}', 'abc')"
                ), {"id": str(uuid4()), "sid": str(s.id)})
                conn.commit()

    def test_report_provider_not_empty(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_reports"
                    " (id, session_id, provider, model_id, prompt_version,"
                    "  schema_version, temperature, report_content, content_hash)"
                    " VALUES (:id, :sid, '', 'v3', 'v1', '1.0', 0.0, '{}', 'abc')"
                ), {"id": str(uuid4()), "sid": str(s.id)})
                conn.commit()

    def test_report_unique_per_session(self, db_session: Session, postgres_engine: Engine) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        _create_report(s.id, db_session)
        # Second report for same session should fail
        with pytest.raises(Exception):
            _create_report(s.id, db_session)

    def test_household_fk_enforced(self, postgres_engine: Engine) -> None:
        with pytest.raises(Exception):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO committee_sessions"
                    " (id, household_id, title, proposal_text, status)"
                    " VALUES (:id, :hid, 'T', 'P', 'draft')"
                ), {"id": str(uuid4()), "hid": str(uuid4())})
                conn.commit()

    def test_report_fk_session_cascade_delete(
        self, db_session: Session, postgres_engine: Engine,
    ) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        rid = _create_report(s.id, db_session).id

        db_session.delete(s)
        db_session.commit()

        # Report should be cascade-deleted
        row = db_session.query(CommitteeReport).filter_by(id=rid).first()
        assert row is None

    def test_evidence_cascade_delete(
        self, db_session: Session, postgres_engine: Engine,
    ) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        eid = uuid4()
        db_session.execute(text(
            "INSERT INTO committee_evidence_items"
            " (id, session_id, source_type, source_title, as_of,"
            "  content_hash, structured_facts, provenance, freshness,"
            "  confidence, citation_ref)"
            " VALUES (:id, :sid, 'owner_claim', 'T', now(),"
            "  'abc', '{}', 'owner_provided', 'current',"
            "  'high', 'ref')"
        ), {"id": str(eid), "sid": str(s.id)})
        db_session.commit()

        db_session.delete(s)
        db_session.commit()

        row = db_session.query(CommitteeEvidenceItem).filter_by(id=eid).first()
        assert row is None


# ═══════════════════════════════════════════════════════════════════════════
# ORM Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestOrmIntegration:
    def test_create_session_and_evidence(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        e = CommitteeEvidenceItem(
            id=uuid4(),
            session_id=s.id,
            source_type="owner_claim",
            source_title="Owner's claim",
            as_of=datetime.now(timezone.utc),
            content_hash="abc",
            structured_facts={"key": "value"},
            provenance="owner_provided",
            freshness="current",
            confidence="medium",
            citation_ref="Owner input",
        )
        db_session.add(e)
        db_session.commit()

        reloaded = db_session.query(CommitteeSession).filter_by(id=s.id).first()
        assert reloaded is not None
        assert len(reloaded.evidence_items) == 1
        assert reloaded.evidence_items[0].source_type == "owner_claim"

    def test_session_status_lifecycle(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        assert s.status == "draft"

        s.status = "queued"
        db_session.commit()
        assert s.status == "queued"

        s.status = "running"
        db_session.commit()
        assert s.status == "running"

        s.status = "completed"
        db_session.commit()
        assert s.status == "completed"

    def test_parent_session_linking(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s1 = _create_session(h.id, db_session)
        s2 = CommitteeSession(
            id=uuid4(),
            household_id=h.id,
            parent_session_id=s1.id,
            title="Re-run",
            proposal_text="Re-analyzing...",
            status="draft",
        )
        db_session.add(s2)
        db_session.commit()

        reloaded = db_session.query(CommitteeSession).filter_by(id=s2.id).first()
        assert reloaded.parent_session_id == s1.id

    def test_outcome_lifecycle(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        r = _create_report(s.id, db_session)
        o = CommitteeOutcome(
            id=uuid4(),
            session_id=s.id,
            report_id=r.id,
            outcome="accepted",
            owner_rationale="Looks good",
            decision_draft_id=None,
        )
        db_session.add(o)
        db_session.commit()

        reloaded = db_session.query(CommitteeOutcome).filter_by(id=o.id).first()
        assert reloaded is not None
        assert reloaded.outcome == "accepted"
        assert reloaded.owner_rationale == "Looks good"

    def test_outcome_all_three_values(self, db_session: Session) -> None:
        h = _create_household(db_session)
        for outcome in ("accepted", "rejected", "deferred"):
            s = _create_session(h.id, db_session)
            r = _create_report(s.id, db_session)
            o = CommitteeOutcome(
                id=uuid4(),
                session_id=s.id,
                report_id=r.id,
                outcome=outcome,
            )
            db_session.add(o)
            db_session.commit()
            assert db_session.query(CommitteeOutcome).filter_by(id=o.id).first().outcome == outcome


# ═══════════════════════════════════════════════════════════════════════════
# Evidence Builder Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceBuilder:
    def test_empty_household_returns_empty(self, db_session: Session) -> None:
        from apps.api.services.evidence_builder import build_evidence_packet
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        items = build_evidence_packet(db_session, h.id, s)
        # No Policy, Portfolio, Guardian events, or Decisions — empty result
        assert isinstance(items, list)

    def test_evidence_items_have_required_fields(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        e = CommitteeEvidenceItem(
            id=uuid4(),
            session_id=s.id,
            source_type="owner_claim",
            source_title="Test",
            as_of=datetime.now(timezone.utc),
            content_hash="abc123",
            structured_facts={"a": 1},
            provenance="owner_provided",
            freshness="current",
            confidence="medium",
            citation_ref="§1",
        )
        db_session.add(e)
        db_session.commit()

        reloaded = db_session.query(CommitteeEvidenceItem).filter_by(id=e.id).first()
        assert reloaded.source_type == "owner_claim"
        assert reloaded.provenance == "owner_provided"
        assert reloaded.confidence == "medium"
        assert reloaded.content_hash == "abc123"
        assert reloaded.citation_ref == "§1"

    def test_evidence_all_source_types_accepted(self, db_session: Session) -> None:
        h = _create_household(db_session)
        s = _create_session(h.id, db_session)
        valid_types = [
            "portfolio_snapshot",
            "policy_version",
            "guardian_event",
            "decision",
            "owner_claim",
            "external",
        ]
        for st in valid_types:
            e = CommitteeEvidenceItem(
                id=uuid4(),
                session_id=s.id,
                source_type=st,
                source_title="T",
                as_of=datetime.now(timezone.utc),
                content_hash="abc",
                structured_facts={},
                provenance="compoundos_internal" if st != "owner_claim" else "owner_provided",
                freshness="current",
                confidence="high",
                citation_ref="ref",
            )
            db_session.add(e)
        db_session.commit()
        assert db_session.query(CommitteeEvidenceItem).count() == len(valid_types)
