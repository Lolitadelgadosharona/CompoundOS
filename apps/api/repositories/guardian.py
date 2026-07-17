"""Guardian data access layer — pure SQLAlchemy query functions."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.models import (
    GuardianCheck,
    GuardianCheckConfirmed,
    GuardianCheckDraft,
    GuardianEvaluationRun,
    GuardianEvent,
    InvestmentPolicy,
    InvestmentPolicyVersion,
    PortfolioSnapshot,
    PortfolioSnapshotHolding,
)

# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------


def get_current_household_id(session: Session) -> Optional[UUID]:
    row = session.execute(
        text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Guardian Check — identity
# ---------------------------------------------------------------------------


def create_check(
    session: Session,
    check_id: UUID,
    household_id: UUID,
    name: str,
    canonical_name: str,
    check_type: str,
) -> GuardianCheck:
    check = GuardianCheck(
        id=check_id,
        household_id=household_id,
        name=name,
        canonical_name=canonical_name,
        check_type=check_type,
    )
    session.add(check)
    session.flush()
    return check


def get_check(session: Session, check_id: UUID) -> Optional[GuardianCheck]:
    return session.get(GuardianCheck, check_id)


def list_checks(session: Session, household_id: UUID) -> Sequence[GuardianCheck]:
    return (
        session.query(GuardianCheck)
        .filter(GuardianCheck.household_id == household_id)
        .order_by(GuardianCheck.created_at)
        .all()
    )


def update_check_status(session: Session, check_id: UUID, status: str) -> None:
    session.execute(
        text("UPDATE guardian_checks SET status = :s, updated_at = :now WHERE id = :id"),
        {"s": status, "id": check_id, "now": datetime.now(timezone.utc)},
    )


def delete_check(session: Session, check_id: UUID) -> None:
    session.execute(
        text("DELETE FROM guardian_checks WHERE id = :id"), {"id": check_id}
    )


def get_check_by_canonical(
    session: Session, household_id: UUID, canonical_name: str
) -> Optional[GuardianCheck]:
    return (
        session.query(GuardianCheck)
        .filter(
            GuardianCheck.household_id == household_id,
            GuardianCheck.canonical_name == canonical_name,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Guardian Check — draft
# ---------------------------------------------------------------------------


def upsert_draft(
    session: Session,
    check_id: UUID,
    *,
    threshold_value: Decimal,
    target_category: Optional[str] = None,
    target_holding_category: Optional[str] = None,
    staleness_days: Optional[int] = None,
    severity: str = "info",
    notes: Optional[str] = None,
) -> GuardianCheckDraft:
    draft = session.get(GuardianCheckDraft, check_id)
    if draft is None:
        draft = GuardianCheckDraft(check_id=check_id, expected_revision=0)
        session.add(draft)
    draft.threshold_value = threshold_value
    draft.target_category = target_category
    draft.target_holding_category = target_holding_category
    draft.staleness_days = staleness_days
    draft.severity = severity
    draft.notes = notes
    draft.expected_revision += 1
    draft.updated_at = datetime.now(timezone.utc)
    session.flush()
    return draft


def get_draft(session: Session, check_id: UUID) -> Optional[GuardianCheckDraft]:
    return session.get(GuardianCheckDraft, check_id)


def delete_draft(session: Session, check_id: UUID) -> None:
    session.execute(
        text("DELETE FROM guardian_check_drafts WHERE check_id = :id"),
        {"id": check_id},
    )


def get_draft_revision(session: Session, check_id: UUID) -> int:
    row = session.execute(
        text(
            "SELECT expected_revision FROM guardian_check_drafts WHERE check_id = :id"
        ),
        {"id": check_id},
    ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Guardian Check — confirmed version
# ---------------------------------------------------------------------------


def create_confirmed_version(
    session: Session,
    *,
    id: UUID,
    check_id: UUID,
    version_number: int,
    check_type: str,
    threshold_value: Decimal,
    severity: str,
    target_category: Optional[str] = None,
    target_holding_category: Optional[str] = None,
    staleness_days: Optional[int] = None,
    notes: Optional[str] = None,
) -> GuardianCheckConfirmed:
    confirmed = GuardianCheckConfirmed(
        id=id,
        check_id=check_id,
        version_number=version_number,
        check_type=check_type,
        threshold_value=threshold_value,
        target_category=target_category,
        target_holding_category=target_holding_category,
        staleness_days=staleness_days,
        severity=severity,
        notes=notes,
    )
    session.add(confirmed)
    session.flush()
    return confirmed


def get_latest_confirmed_version(
    session: Session, check_id: UUID
) -> Optional[GuardianCheckConfirmed]:
    return (
        session.query(GuardianCheckConfirmed)
        .filter(GuardianCheckConfirmed.check_id == check_id)
        .order_by(GuardianCheckConfirmed.version_number.desc())
        .first()
    )


def get_next_version_number(session: Session, check_id: UUID) -> int:
    latest = get_latest_confirmed_version(session, check_id)
    return (latest.version_number + 1) if latest else 1


def list_confirmed_checks(
    session: Session, household_id: UUID
) -> Sequence[GuardianCheckConfirmed]:
    return (
        session.query(GuardianCheckConfirmed)
        .join(GuardianCheck)
        .filter(GuardianCheck.household_id == household_id)
        .all()
    )


def get_confirmed_version(
    session: Session, version_id: UUID
) -> Optional[GuardianCheckConfirmed]:
    return session.get(GuardianCheckConfirmed, version_id)


# ---------------------------------------------------------------------------
# Evaluation — snapshot / policy reads
# ---------------------------------------------------------------------------


def get_current_published_policy(
    session: Session, household_id: UUID
) -> Optional[InvestmentPolicyVersion]:
    return (
        session.query(InvestmentPolicyVersion)
        .join(
            InvestmentPolicy,
            text(
                "investment_policy_versions.policy_id = investment_policies.id"
                " AND investment_policies.household_id = :hid"
            ),
        )
        .params(hid=household_id)
        .filter(
            InvestmentPolicyVersion.status == "published",
            InvestmentPolicyVersion.superseded_at.is_(None),
        )
        .first()
    )


def get_current_portfolio_snapshot(
    session: Session, household_id: UUID
) -> Optional[PortfolioSnapshot]:
    return (
        session.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.status == "current",
            text(
                "portfolio_snapshots.portfolio_id IN ("
                "SELECT id FROM portfolios WHERE household_id = :hid)"
            ),
        )
        .params(hid=household_id)
        .first()
    )


def get_snapshot_holdings(
    session: Session, snapshot_id: UUID
) -> Sequence[PortfolioSnapshotHolding]:
    return (
        session.query(PortfolioSnapshotHolding)
        .filter(PortfolioSnapshotHolding.snapshot_id == snapshot_id)
        .order_by(PortfolioSnapshotHolding.sort_order)
        .all()
    )


def has_any_holdings(session: Session, snapshot_id: UUID) -> bool:
    row = session.execute(
        text(
            "SELECT 1 FROM portfolio_snapshot_holdings"
            " WHERE snapshot_id = :sid LIMIT 1"
        ),
        {"sid": snapshot_id},
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Evaluation — runs
# ---------------------------------------------------------------------------


def create_evaluation_run(
    session: Session,
    *,
    run_id: UUID,
    household_id: UUID,
    status: str,
    checks_evaluated: int,
    events_created: int,
    as_of_date: date,
    skip_reason: Optional[str] = None,
) -> GuardianEvaluationRun:
    run = GuardianEvaluationRun(
        id=run_id,
        household_id=household_id,
        status=status,
        checks_evaluated=checks_evaluated,
        events_created=events_created,
        as_of_date=as_of_date,
        skip_reason=skip_reason,
    )
    session.add(run)
    session.flush()
    return run


def get_evaluation_run(
    session: Session, run_id: UUID
) -> Optional[GuardianEvaluationRun]:
    return session.get(GuardianEvaluationRun, run_id)


def list_evaluation_runs(
    session: Session, household_id: UUID, limit: int = 50
) -> Sequence[GuardianEvaluationRun]:
    return (
        session.query(GuardianEvaluationRun)
        .filter(GuardianEvaluationRun.household_id == household_id)
        .order_by(GuardianEvaluationRun.started_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Evaluation — events
# ---------------------------------------------------------------------------


def insert_event_on_conflict_do_nothing(
    session: Session,
    *,
    evaluation_run_id: UUID,
    household_id: UUID,
    check_id: UUID,
    check_version_id: UUID,
    check_type: str,
    policy_version_id: UUID,
    portfolio_snapshot_id: UUID,
    exceeded: bool = True,
    drift_pp: Optional[Decimal] = None,
    exposure_pct: Optional[Decimal] = None,
    staleness_days_actual: Optional[int] = None,
    as_of_date: date,
) -> Optional[UUID]:
    """INSERT ... ON CONFLICT DO NOTHING RETURNING id. Returns event_id or None."""
    # Build column list dynamically based on check_type
    if check_type in ("drift", "category_exposure"):
        conflict_cols = "check_version_id, policy_version_id, portfolio_snapshot_id"
        conflict_where = "check_type IN ('drift', 'category_exposure')"
    else:
        conflict_cols = "check_version_id, portfolio_snapshot_id, as_of_date"
        conflict_where = "check_type = 'staleness'"

    result = session.execute(
        text(
            "INSERT INTO guardian_events"
            " (id, evaluation_run_id, household_id, check_id, check_version_id,"
            "  check_type, policy_version_id, portfolio_snapshot_id,"
            "  exceeded, drift_pp, exposure_pct, staleness_days_actual, as_of_date)"
            " VALUES (:id, :run_id, :hid, :cid, :cvid,"
            "  :ctype, :pvid, :sid,"
            "  :exceeded, :drift_pp, :exposure_pct, :staleness_days, :as_of)"
            f" ON CONFLICT ({conflict_cols}) WHERE {conflict_where} DO NOTHING"
            " RETURNING id"
        ),
        {
            "id": uuid4(),
            "run_id": evaluation_run_id,
            "hid": household_id,
            "cid": check_id,
            "cvid": check_version_id,
            "ctype": check_type,
            "pvid": policy_version_id,
            "sid": portfolio_snapshot_id,
            "exceeded": exceeded,
            "drift_pp": str(drift_pp) if drift_pp is not None else None,
            "exposure_pct": str(exposure_pct) if exposure_pct is not None else None,
            "staleness_days": staleness_days_actual,
            "as_of": as_of_date,
        },
    )
    row = result.fetchone()
    return row[0] if row else None


def get_events_by_run(
    session: Session, run_id: UUID
) -> Sequence[GuardianEvent]:
    return (
        session.query(GuardianEvent)
        .filter(GuardianEvent.evaluation_run_id == run_id)
        .order_by(GuardianEvent.detected_at)
        .all()
    )


def list_events(
    session: Session, household_id: UUID, limit: int = 50
) -> Sequence[GuardianEvent]:
    return (
        session.query(GuardianEvent)
        .filter(GuardianEvent.household_id == household_id)
        .order_by(GuardianEvent.detected_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def add_audit_event(
    session: Session,
    *,
    id: UUID,
    household_id: UUID,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict,
) -> None:
    import json
    session.execute(
        text(
            "INSERT INTO audit_events (id, household_id, actor, action,"
            " entity_type, entity_id, metadata, occurred_at)"
            " VALUES (:id, :hid, :actor, :action, :etype, :eid, CAST(:meta AS jsonb), :now)"
        ),
        {
            "id": id,
            "hid": household_id,
            "actor": actor,
            "action": action,
            "etype": entity_type,
            "eid": str(entity_id),
            "meta": json.dumps(metadata),
            "now": datetime.now(timezone.utc),
        },
    )


# ---------------------------------------------------------------------------
# Lock helper
# ---------------------------------------------------------------------------


def lock_household(session: Session, household_id: UUID) -> None:
    session.execute(
        text("SELECT id FROM household_profiles WHERE id = :hid FOR UPDATE"),
        {"hid": household_id},
    )
