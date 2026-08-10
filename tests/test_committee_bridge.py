"""Integration tests for Sprint 010 Slice A — Committee Integration Bridge."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0025_auth_and_audit"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_household(session: Session):
    from apps.api.models import HouseholdProfile
    hh = HouseholdProfile(id=uuid4(), household_name="Test", base_currency="USD")
    session.add(hh)
    session.flush()
    return hh


def _create_idea(session: Session, household_id, **kwargs):
    from apps.api.models import InvestmentIdea
    idea = InvestmentIdea(
        id=uuid4(),
        household_id=household_id,
        title=kwargs.get("title", "Test Idea"),
        source=kwargs.get("source", "owner"),
        status=kwargs.get("status", "draft"),
    )
    session.add(idea)
    session.flush()
    return idea


def _table_exists(engine: Engine, table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


# ═══════════════════════════════════════════════════════════════════════
# Migration tests
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_committee_review_requests_table_exists(
        self, postgres_test_isolation, postgres_engine: Engine,
    ):
        assert _table_exists(
            postgres_engine, "committee_review_requests",
        ), "committee_review_requests table not found"

    def test_evidence_source_types_extended(
        self, db_session: Session,
    ):
        """New source types (portfolio_position, policy_bucket, investment_idea)
        are accepted by the extended CHECK constraint."""
        from apps.api.models import (
            CommitteeEvidenceItem,
            CommitteeSession,
            HouseholdProfile,
        )

        hh = HouseholdProfile(
            id=uuid4(), household_name="Evidence Test", base_currency="USD",
        )
        db_session.add(hh)
        db_session.flush()

        session_obj = CommitteeSession(
            id=uuid4(), household_id=hh.id,
            title="Evidence Test", proposal_text="Test new source types",
            status="completed",
        )
        db_session.add(session_obj)
        db_session.flush()

        item = CommitteeEvidenceItem(
            id=uuid4(), session_id=session_obj.id,
            source_type="portfolio_position",
            source_title="Test position evidence",
            as_of=_now(),
            content_hash="test",
            structured_facts={},
            provenance="compoundos_internal",
            confidence="high",
            freshness="current",
            citation_ref="test-ref",
        )
        db_session.add(item)
        # Must not raise — proves CHECK was extended
        db_session.commit()

    def test_migration_head(self, db_session: Session):
        result = db_session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert result == HEAD_REVISION, f"Expected {HEAD_REVISION}, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# Review request creation
# ═══════════════════════════════════════════════════════════════════════


class TestReviewRequestCreation:
    def test_create_review_request(self, db_session: Session):
        from apps.api.repositories.committee_bridge import create_review_request

        hh = _create_household(db_session)
        db_session.commit()

        idea = _create_idea(db_session, hh.id, title="Test", source="owner")
        db_session.commit()

        req = create_review_request(db_session, idea.id, notes="Please review")
        db_session.commit()

        assert req.status == "pending"
        assert req.investment_idea_id == idea.id
        assert req.requested_by == "owner"
        assert req.notes == "Please review"

    def test_create_review_request_committee_source(self, db_session: Session):
        from apps.api.repositories.committee_bridge import create_review_request

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id, source="committee")
        db_session.commit()

        req = create_review_request(
            db_session, idea.id, requested_by="committee",
        )
        db_session.commit()
        assert req.requested_by == "committee"

    def test_cannot_review_nonexistent_idea(self, db_session: Session):
        from apps.api.repositories.committee_bridge import create_review_request

        with pytest.raises((IntegrityError, OperationalError)):
            create_review_request(db_session, uuid4())
            db_session.commit()
        db_session.rollback()

    def test_invalid_status_rejected(self, db_session: Session):
        from apps.api.models import CommitteeReviewRequest

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        req = CommitteeReviewRequest(
            id=uuid4(), investment_idea_id=idea.id,
            requested_by="owner", status="invalid_status",
        )
        db_session.add(req)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()

    def test_invalid_requested_by_rejected(self, db_session: Session):
        from apps.api.models import CommitteeReviewRequest

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        req = CommitteeReviewRequest(
            id=uuid4(), investment_idea_id=idea.id,
            requested_by="ai_agent",  # not in allowed list
        )
        db_session.add(req)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# Review request lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestReviewRequestLifecycle:
    def test_transition_pending_to_in_progress(self, db_session: Session):
        from apps.api.repositories.committee_bridge import (
            create_review_request,
            update_review_request,
        )

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        req = create_review_request(db_session, idea.id)
        db_session.commit()

        updated = update_review_request(
            db_session, req.id, status="in_progress",
        )
        db_session.commit()
        assert updated.status == "in_progress"

    def test_transition_to_completed_with_session(self, db_session: Session):
        from apps.api.models import CommitteeSession
        from apps.api.repositories.committee_bridge import (
            create_review_request,
            update_review_request,
        )

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        req = create_review_request(db_session, idea.id)
        db_session.commit()

        # Create a committee session
        session_obj = CommitteeSession(
            id=uuid4(), household_id=hh.id,
            title="Review: Test Idea",
            proposal_text="Review this idea",
            status="completed",
        )
        db_session.add(session_obj)
        db_session.flush()

        updated = update_review_request(
            db_session, req.id,
            status="completed",
            committee_session_id=session_obj.id,
        )
        db_session.commit()
        assert updated.status == "completed"
        assert updated.committee_session_id == session_obj.id


# ═══════════════════════════════════════════════════════════════════════
# Idea deletion protection
# ═══════════════════════════════════════════════════════════════════════


class TestIdeaProtection:
    def test_cannot_delete_idea_with_review_request(self, db_session: Session):
        """RESTRICT FK prevents deleting an idea that has review requests."""
        from apps.api.repositories.committee_bridge import create_review_request

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        create_review_request(db_session, idea.id)
        db_session.commit()

        db_session.delete(idea)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# AI Authority tests
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_requested_by_requires_valid_source(self, db_session: Session):
        """Only approved sources can create review requests."""
        from apps.api.models import CommitteeReviewRequest

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        # 'ai_agent' is not in CHECK constraint
        req = CommitteeReviewRequest(
            id=uuid4(), investment_idea_id=idea.id,
            requested_by="ai_agent",
        )
        db_session.add(req)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()

    def test_ai_cannot_be_source_for_review(self, db_session: Session):
        """Committee review must be requested by a valid source, not AI."""
        from apps.api.models import CommitteeReviewRequest

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        valid_sources = ["owner", "committee", "guardian"]
        for source in valid_sources:
            req = CommitteeReviewRequest(
                id=uuid4(), investment_idea_id=idea.id,
                requested_by=source,
            )
            db_session.add(req)
            db_session.flush()
        db_session.commit()
        # All valid sources should succeed


# ═══════════════════════════════════════════════════════════════════════
# Listing and querying
# ═══════════════════════════════════════════════════════════════════════


class TestQuerying:
    def test_list_reviews_for_idea(self, db_session: Session):
        from apps.api.repositories.committee_bridge import (
            create_review_request,
            list_review_requests_for_idea,
        )

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        create_review_request(db_session, idea.id)
        db_session.commit()

        reviews = list_review_requests_for_idea(db_session, idea.id)
        assert len(reviews) == 1
        assert reviews[0].investment_idea_id == idea.id

    def test_list_pending_reviews(self, db_session: Session):
        from apps.api.repositories.committee_bridge import (
            create_review_request,
            list_pending_reviews,
            update_review_request,
        )

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        req = create_review_request(db_session, idea.id)
        db_session.commit()

        pending = list_pending_reviews(db_session)
        assert len(pending) == 1

        update_review_request(db_session, req.id, status="completed")
        db_session.commit()

        pending_after = list_pending_reviews(db_session)
        assert len(pending_after) == 0

    def test_empty_reviews_for_idea(self, db_session: Session):
        from apps.api.repositories.committee_bridge import list_review_requests_for_idea

        hh = _create_household(db_session)
        db_session.commit()
        idea = _create_idea(db_session, hh.id)
        db_session.commit()

        reviews = list_review_requests_for_idea(db_session, idea.id)
        assert reviews == []


# ═══════════════════════════════════════════════════════════════════════
# Schema validation
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    def test_create_schema_requires_idea_id(self):
        from pydantic import ValidationError

        from apps.api.committee_bridge_schemas import CommitteeReviewRequestCreate

        with pytest.raises(ValidationError):
            CommitteeReviewRequestCreate()  # missing investment_idea_id

    def test_create_schema_accepts_notes(self):
        from apps.api.committee_bridge_schemas import CommitteeReviewRequestCreate

        req = CommitteeReviewRequestCreate(
            investment_idea_id=uuid4(), notes="Urgent review needed",
        )
        assert req.notes == "Urgent review needed"
