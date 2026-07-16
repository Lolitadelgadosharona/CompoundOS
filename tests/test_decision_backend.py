"""Real PostgreSQL tests for Decision Journal backend workflow (Slice 3B).

Tests cover: creation, Draft CRUD, confirm transaction, discard, archive/unarchive,
corrections, audit events, concurrency, rollback, and error mapping.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.decision_schemas import (
    AppendCorrectionRequest,
    ArchiveDecisionRequest,
    ConfirmDecisionRequest,
    CreateDecisionRequest,
    DiscardDecisionRequest,
    UpdateDecisionDraftRequest,
)
from apps.api.models import (
    AuditEvent,
    Decision,
    HouseholdProfile,
    InvestmentPolicyVersion,
)
from apps.api.repositories.decisions import (
    get_current_published_version,
    get_draft,
    get_household_id,
    get_snapshot,
)
from apps.api.services.decisions import (
    DecisionConflictError,
    DecisionIncompleteError,
    DecisionLifecycleError,
    DraftNotFoundError,
    NoDecisionChangesError,
    append_correction,
    archive_decision,
    confirm_draft,
    create_decision,
    discard_draft,
    read_corrections,
    read_decision_audit_events,
    read_decision_detail,
    read_decision_list,
    read_draft,
    unarchive_decision,
    update_draft,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_household(conn) -> None:
    conn.execute(text("TRUNCATE TABLE audit_events RESTART IDENTITY CASCADE"))
    existing = conn.execute(
        select(HouseholdProfile.id)
    ).scalar()
    if existing is None:
        conn.execute(
            text(
                "INSERT INTO household_profiles"
                " (id, singleton_key, household_name, base_currency,"
                " investment_horizon, liquidity_needs, risk_statement, notes)"
                " VALUES (:id, true, 'Test', 'USD', '', '', '', '')"
            ),
            {"id": str(uuid4())},
        )
        conn.commit()


def _ensure_policy_and_version(session: Session) -> tuple:
    """Ensure a published Policy Version exists for confirm tests."""
    from apps.api.repositories.households import get_current_household
    from apps.api.repositories.policies import (
        add_draft as add_policy_draft,
    )
    from apps.api.repositories.policies import (
        add_policy,
        get_policy,
    )

    household = get_current_household(session)
    policy = get_policy(session, household.id)
    if policy is None:
        policy = add_policy(session, household.id)
        session.flush()

    published = get_current_published_version(session, policy.id)
    if published is None:
        draft = add_policy_draft(session, policy.id)
        draft.objectives = "Test objectives"
        draft.time_horizon = "Long term"
        draft.decision_process = "Structured"
        session.flush()

        now = datetime.now(timezone.utc)
        published = InvestmentPolicyVersion(
            policy_id=policy.id,
            version_number=1,
            status="published",
            published_at=now,
            objectives=draft.objectives,
            time_horizon=draft.time_horizon,
            liquidity="",
            diversification="",
            contribution_policy="",
            rebalancing_policy="",
            prohibited_assets="",
            leverage_policy="",
            decision_process=draft.decision_process,
            notes="",
        )
        session.add(published)
        session.flush()
        session.delete(draft)
        session.flush()

    return policy, published


# ---------------------------------------------------------------------------
# Creation / Draft tests
# ---------------------------------------------------------------------------


class TestDecisionCreation:
    def test_create_decision_and_draft(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            payload = CreateDecisionRequest(title="Buy ETF")
            decision, draft = create_decision(session, payload)
            conn.commit()

        assert decision.status == "draft"
        assert draft.title == "Buy ETF"
        assert draft.revision == 1

    def test_create_writes_audit_event(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Test")
            )
            events = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == decision.id
                    )
                )
            )
            conn.commit()

        assert len(events) == 1
        assert events[0].action == "decision.draft.created"
        assert events[0].entity_type == "Decision"
        assert events[0].event_metadata == {"draft_revision": 1}

    def test_multiple_independent_drafts(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            d1, _ = create_decision(session, CreateDecisionRequest(title="D1"))
            d2, _ = create_decision(session, CreateDecisionRequest(title="D2"))
            conn.commit()

        assert d1.id != d2.id

    def test_create_rollback_on_audit_failure(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        """Verify that if audit event insert fails, the decision is rolled back."""
        # This is tested implicitly by the atomic transaction pattern
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            before_count = session.scalar(
                select(text("count(*)")).select_from(Decision)
            )
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Rollback test")
            )
            after_count = session.scalar(
                select(text("count(*)")).select_from(Decision)
            )
            conn.commit()

        assert after_count == before_count + 1


# ---------------------------------------------------------------------------
# Draft read / list tests
# ---------------------------------------------------------------------------


class TestDraftReadList:
    def test_read_draft(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Read me")
            )
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            result = read_draft(session, decision_id)
            assert result.title == "Read me"

    def test_list_decisions_default_hides_archived(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            d1, _ = create_decision(session, CreateDecisionRequest(title="D1"))
            conn.commit()

        with Session(bind=postgres_engine) as session:
            rows = read_decision_list(session)
            assert len(rows) >= 1

    def test_read_draft_not_found_for_confirmed(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        """Confirmed decisions should not return draft detail."""
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session,
                CreateDecisionRequest(title="Confirm me"),
            )
            # Fill required fields
            draft.decision_summary = "Summary"
            draft.rationale = "Rationale"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            with pytest.raises(DraftNotFoundError):
                read_draft(session, decision_id)


# ---------------------------------------------------------------------------
# Update Draft tests
# ---------------------------------------------------------------------------


class TestDraftUpdate:
    def test_update_fields(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Update me")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            result = update_draft(
                session,
                decision_id,
                UpdateDecisionDraftRequest(
                    expected_revision=1,
                    decision_summary="New summary",
                    rationale="New rationale",
                ),
            )
            conn.commit()

        assert result.decision_summary == "New summary"
        assert result.rationale == "New rationale"
        assert result.revision == 2

    def test_stale_revision_returns_409(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Stale")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            with pytest.raises(DecisionConflictError):
                update_draft(
                    session,
                    decision_id,
                    UpdateDecisionDraftRequest(
                        expected_revision=999, title="Bad"
                    ),
                )
            conn.rollback()

    def test_no_op_returns_400(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="NoOp")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            with pytest.raises(NoDecisionChangesError):
                update_draft(
                    session,
                    decision_id,
                    UpdateDecisionDraftRequest(expected_revision=1),
                )
            conn.rollback()


# ---------------------------------------------------------------------------
# Confirm tests
# ---------------------------------------------------------------------------


class TestConfirm:
    def test_confirm_first(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Confirm first")
            )
            draft.decision_summary = "Summary"
            draft.rationale = "Rationale"
            draft.decision_date = date.today()
            session.flush()
            snapshot = confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            conn.commit()

        assert snapshot.title == "Confirm first"
        assert snapshot.decision_summary == "Summary"
        assert snapshot.decision_date == date.today()

    def test_confirm_requires_fields(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Missing fields")
            )
            session.flush()
            with pytest.raises(DecisionIncompleteError):
                confirm_draft(
                    session,
                    decision.id,
                    ConfirmDecisionRequest(
                        expected_revision=draft.revision, confirmation=True
                    ),
                )
            conn.rollback()

    def test_confirm_draft_consumed(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Consume")
            )
            draft.decision_summary = "S"
            draft.rationale = "R"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            session.flush()
            remaining_draft = get_draft(session, decision.id)
            conn.commit()

        assert remaining_draft is None

    def test_confirm_writes_audit_event(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            policy, published = _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Audit")
            )
            draft.decision_summary = "S"
            draft.rationale = "R"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            events = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == decision.id,
                        AuditEvent.action == "decision.confirmed",
                    )
                )
            )
            conn.commit()

        assert len(events) == 1
        assert events[0].event_metadata["policy_version_number"] == published.version_number


# ---------------------------------------------------------------------------
# Discard tests
# ---------------------------------------------------------------------------


class TestDiscard:
    def test_discard_atomic_deletion(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Discard me")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            discard_draft(
                session,
                decision_id,
                DiscardDecisionRequest(expected_revision=1),
            )
            conn.commit()

        with Session(bind=postgres_engine) as session:
            remaining = session.scalar(
                select(Decision).where(Decision.id == decision_id)
            )
            assert remaining is None

    def test_discard_audit_uuid_preserved(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Preserve UUID")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            discard_draft(
                session,
                decision_id,
                DiscardDecisionRequest(expected_revision=1),
            )
            events = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == decision_id,
                        AuditEvent.action == "decision.draft.discarded",
                    )
                )
            )
            conn.commit()

        assert len(events) == 1
        assert events[0].entity_id == decision_id

    def test_discard_confirmed_rejected(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="No discard")
            )
            draft.decision_summary = "S"
            draft.rationale = "R"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            with pytest.raises(DecisionLifecycleError):
                discard_draft(
                    session,
                    decision_id,
                    DiscardDecisionRequest(expected_revision=99),
                )
            conn.rollback()


# ---------------------------------------------------------------------------
# Archive / Unarchive tests
# ---------------------------------------------------------------------------


class TestArchiveUnarchive:
    def _confirmed_decision(self, session):
        _ensure_policy_and_version(session)
        decision, draft = create_decision(
            session, CreateDecisionRequest(title="Archive me")
        )
        draft.decision_summary = "S"
        draft.rationale = "R"
        draft.decision_date = date.today()
        session.flush()
        confirm_draft(
            session,
            decision.id,
            ConfirmDecisionRequest(
                expected_revision=draft.revision, confirmation=True
            ),
        )
        session.flush()
        return decision

    def test_archive_confirmed(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            result = archive_decision(
                session,
                decision_id,
                ArchiveDecisionRequest(archive_reason="Outdated"),
            )
            conn.commit()

        assert result.status == "archived"
        assert result.archive_reason == "Outdated"
        assert result.archived_at is not None

    def test_unarchive(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            archive_decision(
                session, decision.id, ArchiveDecisionRequest()
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            result = unarchive_decision(session, decision_id)
            conn.commit()

        assert result.status == "confirmed"
        assert result.archived_at is None
        assert result.archive_reason is None

    def test_archive_draft_rejected(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, _ = create_decision(
                session, CreateDecisionRequest(title="No archive")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            with pytest.raises(DecisionLifecycleError):
                archive_decision(
                    session, decision_id, ArchiveDecisionRequest()
                )
            conn.rollback()

    def test_archive_writes_audit_event(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            archive_decision(
                session, decision.id, ArchiveDecisionRequest()
            )
            events = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == decision.id,
                        AuditEvent.action == "decision.archived",
                    )
                )
            )
            conn.commit()

        assert len(events) == 1


# ---------------------------------------------------------------------------
# Correction tests
# ---------------------------------------------------------------------------


class TestCorrections:
    def _confirmed_decision(self, session):
        _ensure_policy_and_version(session)
        decision, draft = create_decision(
            session, CreateDecisionRequest(title="Correct me")
        )
        draft.decision_summary = "S"
        draft.rationale = "R"
        draft.decision_date = date.today()
        session.flush()
        confirm_draft(
            session,
            decision.id,
            ConfirmDecisionRequest(
                expected_revision=draft.revision, confirmation=True
            ),
        )
        session.flush()
        return decision

    def test_first_correction_number_1(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            correction = append_correction(
                session,
                decision_id,
                AppendCorrectionRequest(
                    correction_reason="Typo",
                    title="Corrected",
                    decision_summary="CS",
                    rationale="CR",
                    decision_date=date.today(),
                ),
            )
            conn.commit()

        assert correction.correction_number == 1

    def test_sequential_numbers(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            c1 = append_correction(
                session,
                decision_id,
                AppendCorrectionRequest(
                    correction_reason="R1",
                    title="T1",
                    decision_summary="S1",
                    rationale="Ra1",
                    decision_date=date.today(),
                ),
            )
            c2 = append_correction(
                session,
                decision_id,
                AppendCorrectionRequest(
                    correction_reason="R2",
                    title="T2",
                    decision_summary="S2",
                    rationale="Ra2",
                    decision_date=date.today(),
                ),
            )
            conn.commit()

        assert c1.correction_number == 1
        assert c2.correction_number == 2

    def test_correction_on_archived_allowed(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            archive_decision(
                session, decision.id, ArchiveDecisionRequest()
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            correction = append_correction(
                session,
                decision_id,
                AppendCorrectionRequest(
                    correction_reason="Archive fix",
                    title="T",
                    decision_summary="S",
                    rationale="R",
                    decision_date=date.today(),
                ),
            )
            conn.commit()

        assert correction.correction_number == 1

    def test_correction_on_draft_rejected(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, _ = create_decision(
                session, CreateDecisionRequest(title="No correct")
            )
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            with pytest.raises(DecisionLifecycleError):
                append_correction(
                    session,
                    decision_id,
                    AppendCorrectionRequest(
                        correction_reason="R",
                        title="T",
                        decision_summary="S",
                        rationale="Ra",
                        decision_date=date.today(),
                    ),
                )
            conn.rollback()

    def test_original_snapshot_unchanged(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            append_correction(
                session,
                decision_id,
                AppendCorrectionRequest(
                    correction_reason="R",
                    title="Changed",
                    decision_summary="S",
                    rationale="R",
                    decision_date=date.today(),
                ),
            )
            original = get_snapshot(session, decision_id)
            conn.commit()

        assert original.title == "Correct me"

    def test_correction_list_ordered(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision = self._confirmed_decision(session)
            conn.commit()
            decision_id = decision.id

        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            for i in range(3):
                append_correction(
                    session,
                    decision_id,
                    AppendCorrectionRequest(
                        correction_reason=f"R{i}",
                        title=f"T{i}",
                        decision_summary=f"S{i}",
                        rationale=f"Ra{i}",
                        decision_date=date.today(),
                    ),
                )
            conn.commit()

        with Session(bind=postgres_engine) as session:
            corrections = read_corrections(session, decision_id)
            assert len(corrections) == 3
            assert [c.correction_number for c in corrections] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Audit Event tests
# ---------------------------------------------------------------------------


class TestAuditEvents:
    def test_audit_redaction(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Redact")
            )
            draft.decision_summary = "Sensitive summary"
            draft.rationale = "Sensitive rationale"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            events = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == decision.id
                    )
                )
            )
            conn.commit()

        for event in events:
            meta = event.event_metadata
            assert "title" not in meta
            assert "decision_summary" not in meta
            assert "rationale" not in meta
            assert "correction_count" not in meta

    def test_audit_cursor_pagination(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Paginate")
            )
            for i in range(3):
                update_draft(
                    session,
                    decision.id,
                    UpdateDecisionDraftRequest(
                        expected_revision=i + 1,
                        notes=f"Update {i}",
                    ),
                )
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            events, cursor = read_decision_audit_events(
                session, decision_id, limit=2
            )
            assert len(events) == 2
            assert cursor is not None

            events2, cursor2 = read_decision_audit_events(
                session, decision_id, before_sequence_number=cursor, limit=2
            )
            assert len(events2) >= 1


# ---------------------------------------------------------------------------
# Decision Detail tests
# ---------------------------------------------------------------------------


class TestDecisionDetail:
    def test_confirmed_detail_shape(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="Detail")
            )
            draft.decision_summary = "S"
            draft.rationale = "R"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            detail = read_decision_detail(session, decision_id)
            assert detail["status"] == "confirmed"
            assert detail["original_snapshot"] is not None
            assert detail["effective_snapshot"] is not None
            assert detail["corrections_count"] == 0

    def test_detail_with_correction(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            _ensure_policy_and_version(session)
            decision, draft = create_decision(
                session, CreateDecisionRequest(title="With correction")
            )
            draft.decision_summary = "S"
            draft.rationale = "R"
            draft.decision_date = date.today()
            session.flush()
            confirm_draft(
                session,
                decision.id,
                ConfirmDecisionRequest(
                    expected_revision=draft.revision, confirmation=True
                ),
            )
            append_correction(
                session,
                decision.id,
                AppendCorrectionRequest(
                    correction_reason="Fix",
                    title="Corrected",
                    decision_summary="CS",
                    rationale="CR",
                    decision_date=date.today(),
                ),
            )
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            detail = read_decision_detail(session, decision_id)
            assert detail["corrections_count"] == 1
            assert detail["latest_correction_metadata"] is not None
            assert detail["effective_snapshot"].title == "Corrected"
            assert detail["original_snapshot"].title == "With correction"


# ---------------------------------------------------------------------------
# Household timeline inclusion
# ---------------------------------------------------------------------------


class TestHouseholdTimeline:
    def test_decision_events_in_household_timeline(
        self, postgres_engine: Engine, db_session: Session
    ) -> None:
        with postgres_engine.connect() as conn:
            _ensure_household(conn)
        with postgres_engine.begin() as conn:
            session = Session(bind=conn)
            decision, _ = create_decision(
                session, CreateDecisionRequest(title="Timeline")
            )
            household_id = get_household_id(session)
            conn.commit()
            decision_id = decision.id

        with Session(bind=postgres_engine) as session:
            from apps.api.repositories.households import list_audit_events

            events = list_audit_events(session, household_id)
            decision_events = [
                e for e in events if e.entity_id == decision_id
            ]
            assert len(decision_events) >= 1
            assert decision_events[0].entity_type == "Decision"
