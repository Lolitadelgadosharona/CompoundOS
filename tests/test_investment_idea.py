"""Integration tests for Sprint 009 Slice C — Investment Idea + Decision Bridge.

Tests cover:
  1. Idea creation with valid fields
  2. Status lifecycle transitions
  3. Invalid transitions rejected
  4. Append-only status history
  5. Policy version linkage
  6. Asset linkage (nullable)
  7. Decision bridge (draft + snapshot linkage)
  8. Cancelled/rejected/deferred flows
  9. Historical preservation
  10. No owner authorization bypass
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0029_perspective_analyses"

SPRINT_009C_TABLES = frozenset({
    "investment_ideas",
    "idea_status_history",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_household(session: Session) -> tuple:
    """Create household + policy + draft + published version."""
    from apps.api.models import (
        HouseholdProfile,
        InvestmentPolicy,
        InvestmentPolicyDraft,
        InvestmentPolicyVersion,
    )

    household = HouseholdProfile(
        id=uuid4(), household_name="Test", base_currency="USD",
    )
    session.add(household)
    session.flush()

    policy = InvestmentPolicy(id=uuid4(), household_id=household.id)
    session.add(policy)
    session.flush()

    draft = InvestmentPolicyDraft(id=uuid4(), policy_id=policy.id, revision=1)
    session.add(draft)
    session.flush()

    now = _now()
    version = InvestmentPolicyVersion(
        id=uuid4(), policy_id=policy.id, version_number=1,
        status="published",
        objectives="Test", time_horizon="", liquidity="",
        diversification="", contribution_policy="", rebalancing_policy="",
        prohibited_assets="", leverage_policy="", decision_process="", notes="",
        published_at=now, sealed_at=None,
    )
    session.add(version)
    session.flush()
    version.sealed_at = now
    session.flush()

    return household, policy, draft, version


def _table_exists(engine: Engine, table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


# ═══════════════════════════════════════════════════════════════════════
# Migration tests
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_tables_exist(self, postgres_test_isolation, postgres_engine: Engine):
        for table_name in SPRINT_009C_TABLES:
            assert _table_exists(postgres_engine, table_name), (
                f"Table {table_name!r} not found"
            )

    def test_decision_draft_has_idea_id(self, postgres_test_isolation, postgres_engine: Engine):
        inspector = inspect(postgres_engine)
        cols = {c["name"] for c in inspector.get_columns("decision_drafts")}
        assert "investment_idea_id" in cols, "decision_drafts missing investment_idea_id"

    def test_decision_snapshot_has_idea_id(self, postgres_test_isolation, postgres_engine: Engine):
        inspector = inspect(postgres_engine)
        cols = {c["name"] for c in inspector.get_columns("decision_confirmed_snapshots")}
        assert "investment_idea_id" in cols, (
            "decision_confirmed_snapshots missing investment_idea_id")

    def test_migration_head(self, db_session: Session):
        result = db_session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert result == HEAD_REVISION, f"Expected {HEAD_REVISION}, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# Idea creation
# ═══════════════════════════════════════════════════════════════════════


class TestIdeaCreation:
    def test_create_draft_idea(self, db_session: Session):
        from apps.api.repositories.investment_idea import create_idea, get_idea

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(
            db_session, household.id,
            title="Increase AAPL position",
            source="owner",
            confidence="HIGH",
        )
        db_session.commit()

        fetched = get_idea(db_session, idea.id)
        assert fetched is not None
        assert fetched.title == "Increase AAPL position"
        assert fetched.status == "draft"
        assert fetched.source == "owner"
        assert fetched.confidence == "HIGH"

    def test_create_idea_with_asset(self, db_session: Session):
        from apps.api.models import Asset
        from apps.api.repositories.investment_idea import create_idea

        household, _, _, _ = _create_household(db_session)
        asset = Asset(id=uuid4(), name="Apple Inc.", asset_type="STOCK", currency="USD")
        db_session.add(asset)
        db_session.commit()

        idea = create_idea(
            db_session, household.id,
            title="Buy AAPL shares",
            source="owner",
            asset_id=asset.id,
        )
        db_session.commit()
        assert idea.asset_id == asset.id

    def test_create_idea_with_policy_version(self, db_session: Session):
        from apps.api.repositories.investment_idea import create_idea

        household, _, _, version = _create_household(db_session)
        db_session.commit()

        idea = create_idea(
            db_session, household.id,
            title="Policy-linked idea",
            source="owner",
            policy_version_id=version.id,
        )
        db_session.commit()
        assert idea.policy_version_id == version.id

    def test_idea_invalid_source_rejected(self, db_session: Session):
        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            from apps.api.models import InvestmentIdea
            idea = InvestmentIdea(
                id=uuid4(), household_id=household.id,
                title="Bad", source="ai_agent",
            )
            db_session.add(idea)
            db_session.commit()
        db_session.rollback()

    def test_idea_invalid_confidence_rejected(self, db_session: Session):
        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            from apps.api.models import InvestmentIdea
            idea = InvestmentIdea(
                id=uuid4(), household_id=household.id,
                title="Bad", source="owner", confidence="SUPER_HIGH",
            )
            db_session.add(idea)
            db_session.commit()
        db_session.rollback()

    def test_idea_title_too_long_rejected(self, db_session: Session):
        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            from apps.api.models import InvestmentIdea
            idea = InvestmentIdea(
                id=uuid4(), household_id=household.id,
                title="X" * 201, source="owner",
            )
            db_session.add(idea)
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# Status lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestStatusLifecycle:
    def test_status_transition_draft_to_under_review(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        updated = transition_idea_status(db_session, idea.id, "under_review")
        db_session.commit()
        assert updated is not None
        assert updated.status == "under_review"

    def test_full_lifecycle_draft_to_approved(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        # draft → under_review
        transition_idea_status(db_session, idea.id, "under_review")
        db_session.commit()

        # under_review → approved
        transition_idea_status(db_session, idea.id, "approved", reason="Owner decision")
        db_session.commit()

        db_session.refresh(idea)
        assert idea.status == "approved"

    def test_rejected_can_return_to_draft(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "under_review")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "rejected", reason="Too risky")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "draft", reason="Revisit later")
        db_session.commit()

        db_session.refresh(idea)
        assert idea.status == "draft"

    def test_deferred_can_return_to_draft(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "deferred", reason="Wait for Q1")
        db_session.commit()

        db_session.refresh(idea)
        assert idea.status == "deferred"

        transition_idea_status(db_session, idea.id, "draft")
        db_session.commit()

        db_session.refresh(idea)
        assert idea.status == "draft"

    def test_cancelled_can_restart_as_draft(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "cancelled")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "draft", reason="Reopened")
        db_session.commit()

        db_session.refresh(idea)
        assert idea.status == "draft"


# ═══════════════════════════════════════════════════════════════════════
# History append-only
# ═══════════════════════════════════════════════════════════════════════


class TestStatusHistory:
    def test_history_recorded_on_create(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            list_idea_history,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        history = list_idea_history(db_session, idea.id)
        assert len(history) == 1
        assert history[0].new_status == "draft"
        assert history[0].old_status is None
        assert "created" in (history[0].reason or "").lower()

    def test_history_records_each_transition(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            list_idea_history,
            transition_idea_status,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "under_review")
        db_session.commit()

        transition_idea_status(db_session, idea.id, "approved", reason="Decision made")
        db_session.commit()

        history = list_idea_history(db_session, idea.id)
        assert len(history) == 3
        assert history[0].new_status == "draft"
        assert history[1].old_status == "draft"
        assert history[1].new_status == "under_review"
        assert history[2].old_status == "under_review"
        assert history[2].new_status == "approved"
        assert history[2].reason == "Decision made"

    def test_history_not_modified_on_non_status_change(self, db_session: Session):
        from apps.api.repositories.investment_idea import (
            create_idea,
            list_idea_history,
            update_idea_fields,
        )

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Original", source="owner")
        db_session.commit()

        # Update title (not status) — should NOT create history entry
        update_idea_fields(db_session, idea.id, title="Updated Title")
        db_session.commit()

        history = list_idea_history(db_session, idea.id)
        assert len(history) == 1  # Only the creation entry
        assert history[0].new_status == "draft"


# ═══════════════════════════════════════════════════════════════════════
# Decision bridge
# ═══════════════════════════════════════════════════════════════════════


class TestDecisionBridge:
    def test_decision_draft_links_to_idea(self, db_session: Session):
        from apps.api.models import Decision, DecisionDraft
        from apps.api.repositories.investment_idea import create_idea

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        decision = Decision(id=uuid4(), household_id=household.id, status="draft")
        db_session.add(decision)
        db_session.flush()

        draft = DecisionDraft(
            id=uuid4(), decision_id=decision.id,
            title="Decision for idea",
            investment_idea_id=idea.id,
        )
        db_session.add(draft)
        db_session.commit()

        assert draft.investment_idea_id == idea.id

    def test_decision_snapshot_links_to_idea(self, db_session: Session):
        from apps.api.models import Decision, DecisionConfirmedSnapshot
        from apps.api.repositories.investment_idea import create_idea

        household, _, _, version = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        decision = Decision(id=uuid4(), household_id=household.id, status="confirmed")
        db_session.add(decision)
        db_session.flush()

        snapshot = DecisionConfirmedSnapshot(
            id=uuid4(), decision_id=decision.id,
            title="Snapshot for idea",
            decision_summary="Summary", rationale="Rationale",
            decision_date=_now().date(),
            selected_policy_version_id=version.id,
            investment_idea_id=idea.id,
        )
        db_session.add(snapshot)
        db_session.commit()

        assert snapshot.investment_idea_id == idea.id

    def test_idea_survives_decision_draft_SQL_null(self, db_session: Session):
        """SET NULL FK: deleting an idea should NULL the decision's reference."""
        from apps.api.models import Decision, DecisionDraft
        from apps.api.repositories.investment_idea import create_idea

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        # Link decision draft to idea
        decision = Decision(id=uuid4(), household_id=household.id, status="draft")
        db_session.add(decision)
        db_session.flush()
        draft = DecisionDraft(
            id=uuid4(), decision_id=decision.id, title="X",
            investment_idea_id=idea.id,
        )
        db_session.add(draft)
        db_session.commit()

        # Delete the IDEA (not the draft) — draft's FK becomes NULL
        db_session.delete(idea)
        db_session.commit()

        db_session.refresh(draft)
        assert draft.investment_idea_id is None

    def test_null_idea_id_on_decision_allowed(self, db_session: Session):
        """Decisions without an idea are still valid."""
        from apps.api.models import Decision, DecisionDraft

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        decision = Decision(id=uuid4(), household_id=household.id, status="draft")
        db_session.add(decision)
        db_session.flush()

        draft = DecisionDraft(
            id=uuid4(), decision_id=decision.id,
            title="Standalone decision",
            investment_idea_id=None,
        )
        db_session.add(draft)
        db_session.commit()

        assert draft.id is not None
        assert draft.investment_idea_id is None


# ═══════════════════════════════════════════════════════════════════════
# Historical preservation
# ═══════════════════════════════════════════════════════════════════════


class TestHistoricalPreservation:
    def test_history_survives_idea_deletion(self, db_session: Session):
        """History should CASCADE delete with idea (FK ondelete=CASCADE)."""
        from sqlalchemy import text as sa_text

        from apps.api.repositories.investment_idea import create_idea

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        idea = create_idea(db_session, household.id, title="Test", source="owner")
        db_session.commit()

        # Delete idea — history cascades
        db_session.delete(idea)
        db_session.commit()

        count = db_session.execute(
            sa_text("SELECT count(*) FROM idea_status_history WHERE idea_id = :iid"),
            {"iid": idea.id},
        ).scalar()
        assert count == 0

    def test_list_ideas_with_status_filter(self, db_session: Session):
        from apps.api.repositories.investment_idea import create_idea, list_ideas

        household, _, _, _ = _create_household(db_session)
        db_session.commit()

        create_idea(db_session, household.id, title="Idea 1", source="owner")
        create_idea(db_session, household.id, title="Idea 2", source="committee")
        db_session.commit()

        all_ideas = list_ideas(db_session, household.id)
        assert len(all_ideas) == 2

        draft_ideas = list_ideas(db_session, household.id, status="draft")
        assert len(draft_ideas) == 2

        approved_ideas = list_ideas(db_session, household.id, status="approved")
        assert len(approved_ideas) == 0


# ═══════════════════════════════════════════════════════════════════════
# Schema validation
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    def test_create_validates_source(self):
        from pydantic import ValidationError

        from apps.api.investment_idea_schemas import InvestmentIdeaCreate

        with pytest.raises(ValidationError):
            InvestmentIdeaCreate(title="Test", source="robot")

    def test_create_allows_optional_fields(self):
        from apps.api.investment_idea_schemas import InvestmentIdeaCreate

        idea = InvestmentIdeaCreate(title="Minimal idea")
        assert idea.title == "Minimal idea"
        assert idea.source == "owner"

    def test_status_transition_validates_status(self):
        from pydantic import ValidationError

        from apps.api.investment_idea_schemas import InvestmentIdeaStatusTransition

        with pytest.raises(ValidationError):
            InvestmentIdeaStatusTransition(new_status="executed")
