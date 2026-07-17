"""Guardian service layer — check lifecycle, evaluation engine (Sprint 004 Slice B)."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.guardian_schemas import (
    canonicalize_name,
)
from apps.api.models import (
    GuardianCheck,
    GuardianCheckConfirmed,
    GuardianCheckDraft,
    GuardianEvaluationRun,
    GuardianEvent,
    PortfolioSnapshotHolding,
)
from apps.api.repositories.guardian import (
    add_audit_event,
    create_check,
    create_confirmed_version,
    create_evaluation_run,
    delete_check,
    delete_draft,
    get_check,
    get_check_by_canonical,
    get_confirmed_version,
    get_current_household_id,
    get_current_portfolio_snapshot,
    get_current_published_policy,
    get_draft,
    get_draft_revision,
    get_evaluation_run,
    get_events_by_run,
    get_latest_confirmed_version,
    get_next_version_number,
    get_snapshot_holdings,
    has_any_holdings,
    insert_event,
    list_checks,
    list_confirmed_checks,
    list_evaluation_runs,
    list_events,
    lock_household,
    update_check_status,
    upsert_draft,
)

# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class HouseholdRequiredError(Exception):
    """No household exists."""


class CheckNotFoundError(Exception):
    """Check identity not found."""


class DraftNotFoundError(Exception):
    """Check has no draft."""


class DraftConflictError(Exception):
    """Expected revision mismatch."""


class ParentDeletedError(Exception):
    """Draft's parent check was deleted (orphaned)."""


class NameConflictError(Exception):
    """Canonicalized name already exists in household."""


class CheckNotDraftError(Exception):
    """Check is not in draft status."""


class CheckAlreadyConfirmedError(Exception):
    """A confirmed version already exists with this version number."""


class InvalidCheckTypeFieldsError(Exception):
    """Required/forbidden fields mismatch for check type."""


class ConfirmRequiresDraftError(Exception):
    """Cannot confirm without an existing draft."""


# ---------------------------------------------------------------------------
# Per-type field validation
# ---------------------------------------------------------------------------


def _validate_draft_fields(
    check_type: str,
    threshold_value: Decimal,
    target_category: Optional[str],
    target_holding_category: Optional[str],
    staleness_days: Optional[int],
) -> None:
    """Enforce required/forbidden fields per check_type per Technical Design."""
    if check_type == "drift":
        if not target_category or not target_holding_category:
            raise InvalidCheckTypeFieldsError(
                "Drift checks require target_category and target_holding_category"
            )
        if staleness_days is not None:
            raise InvalidCheckTypeFieldsError(
                "Drift checks must not set staleness_days"
            )
    elif check_type == "category_exposure":
        if not target_holding_category:
            raise InvalidCheckTypeFieldsError(
                "Category exposure checks require target_holding_category"
            )
        if target_category is not None:
            raise InvalidCheckTypeFieldsError(
                "Category exposure checks must not set target_category"
            )
        if staleness_days is not None:
            raise InvalidCheckTypeFieldsError(
                "Category exposure checks must not set staleness_days"
            )
    elif check_type == "staleness":
        if staleness_days is None:
            raise InvalidCheckTypeFieldsError(
                "Staleness checks require staleness_days"
            )
        if target_category is not None or target_holding_category is not None:
            raise InvalidCheckTypeFieldsError(
                "Staleness checks must not set target_category or target_holding_category"
            )


# ---------------------------------------------------------------------------
# Check lifecycle
# ---------------------------------------------------------------------------


def create_guardian_check(
    session: Session,
    *,
    household_id: UUID,
    name: str,
    check_type: str,
    threshold_value: Decimal,
    severity: str = "info",
    target_category: Optional[str] = None,
    target_holding_category: Optional[str] = None,
    staleness_days: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[GuardianCheck, GuardianCheckDraft]:
    """Create a new Guardian check identity + draft. Atomic."""
    canonical = canonicalize_name(name)
    existing = get_check_by_canonical(session, household_id, canonical)
    if existing is not None:
        raise NameConflictError(
            f"A check with the name '{existing.name}' already exists"
        )
    _validate_draft_fields(
        check_type, threshold_value, target_category,
        target_holding_category, staleness_days,
    )
    check_id = uuid4()
    now = datetime.now(timezone.utc)
    check = create_check(
        session, check_id, household_id, name=name.strip(),
        canonical_name=canonical, check_type=check_type,
    )
    draft = upsert_draft(
        session, check_id,
        threshold_value=threshold_value,
        target_category=target_category,
        target_holding_category=target_holding_category,
        staleness_days=staleness_days,
        severity=severity,
        notes=notes,
    )
    add_audit_event(
        session,
        id=uuid4(), household_id=household_id,
        actor="owner", action="guardian.check.created",
        entity_type="guardian_check", entity_id=str(check_id),
        metadata={"name": check.name, "check_type": check_type},
    )
    return check, draft


def get_check_detail(
    session: Session, check_id: UUID
) -> dict:
    """Return full check detail: identity + draft + latest confirmed."""
    check = get_check(session, check_id)
    if check is None:
        raise CheckNotFoundError(f"Check {check_id} not found")
    draft = get_draft(session, check_id)
    latest = get_latest_confirmed_version(session, check_id)
    return {
        "identity": check,
        "draft": draft,
        "latest_version": latest,
    }


def update_guardian_draft(
    session: Session,
    *,
    check_id: UUID,
    expected_revision: int,
    threshold_value: Optional[Decimal] = None,
    target_category: Optional[str] = None,
    target_holding_category: Optional[str] = None,
    staleness_days: Optional[int] = None,
    severity: Optional[str] = None,
    notes: Optional[str] = None,
) -> GuardianCheckDraft:
    """Update draft fields with optimistic revision check."""
    check = get_check(session, check_id)
    if check is None:
        raise CheckNotFoundError(f"Check {check_id} not found")
    current_draft = get_draft(session, check_id)
    if current_draft is None:
        raise DraftNotFoundError("No draft to update")
    current_revision = current_draft.expected_revision
    if expected_revision != current_revision:
        raise DraftConflictError(
            f"Expected revision {expected_revision}, current is {current_revision}"
        )
    new_threshold = (
        threshold_value if threshold_value is not None
        else current_draft.threshold_value
    )
    new_target_cat = (
        target_category if target_category is not None
        else current_draft.target_category
    )
    new_holding_cat = (
        target_holding_category if target_holding_category is not None
        else current_draft.target_holding_category
    )
    new_staleness = (
        staleness_days if staleness_days is not None
        else current_draft.staleness_days
    )
    new_severity = (
        severity if severity is not None
        else current_draft.severity
    )
    new_notes = (
        notes if notes is not None
        else current_draft.notes
    )
    _validate_draft_fields(
        check.check_type, new_threshold,
        new_target_cat, new_holding_cat, new_staleness,
    )
    return upsert_draft(
        session, check_id,
        threshold_value=new_threshold,
        target_category=new_target_cat,
        target_holding_category=new_holding_cat,
        staleness_days=new_staleness,
        severity=new_severity,
        notes=new_notes,
    )


def confirm_guardian_check(
    session: Session,
    *,
    check_id: UUID,
    expected_revision: int,
) -> GuardianCheckConfirmed:
    """Confirm draft → immutable confirmed version."""
    check = get_check(session, check_id)
    if check is None:
        raise CheckNotFoundError(f"Check {check_id} not found")
    draft = get_draft(session, check_id)
    if draft is None:
        raise ConfirmRequiresDraftError("No draft to confirm")
    if draft.expected_revision != expected_revision:
        raise DraftConflictError(
            f"Expected revision {expected_revision}, "
            f"draft is at {draft.expected_revision}"
        )
    _validate_draft_fields(
        check.check_type, draft.threshold_value,
        draft.target_category, draft.target_holding_category,
        draft.staleness_days,
    )
    version_number = get_next_version_number(session, check_id)
    confirmed = create_confirmed_version(
        session,
        id=uuid4(),
        check_id=check_id,
        version_number=version_number,
        check_type=check.check_type,
        threshold_value=draft.threshold_value,
        target_category=draft.target_category,
        target_holding_category=draft.target_holding_category,
        staleness_days=draft.staleness_days,
        severity=draft.severity,
        notes=draft.notes,
    )
    update_check_status(session, check_id, "confirmed")
    add_audit_event(
        session,
        id=uuid4(), household_id=check.household_id,
        actor="owner", action="guardian.check.confirmed",
        entity_type="guardian_check", entity_id=str(check_id),
        metadata={
            "version_number": version_number,
            "check_type": check.check_type,
        },
    )
    return confirmed


def discard_guardian_check(
    session: Session, check_id: UUID
) -> None:
    """Discard: delete identity+draft if never confirmed; delete draft only if confirmed exists."""
    check = get_check(session, check_id)
    if check is None:
        raise CheckNotFoundError(f"Check {check_id} not found")
    has_confirmed = get_latest_confirmed_version(session, check_id) is not None
    if has_confirmed:
        delete_draft(session, check_id)
        update_check_status(session, check_id, "draft")
        add_audit_event(
            session,
            id=uuid4(), household_id=check.household_id,
            actor="owner", action="guardian.check.draft_discarded",
            entity_type="guardian_check", entity_id=str(check_id),
            metadata={"retained_confirmed": True},
        )
    else:
        delete_draft(session, check_id)
        delete_check(session, check_id)
        add_audit_event(
            session,
            id=uuid4(), household_id=check.household_id,
            actor="owner", action="guardian.check.deleted",
            entity_type="guardian_check", entity_id=str(check_id),
            metadata={"had_confirmed": False},
        )


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


def _compute_total_value(holdings: Sequence[PortfolioSnapshotHolding]) -> Decimal:
    """Sum of all holding total_values. Returns Decimal."""
    total = Decimal("0")
    for h in holdings:
        total += h.total_value if h.total_value else Decimal("0")
    return total


def _build_category_map(
    holdings: Sequence[PortfolioSnapshotHolding],
) -> dict[str, Decimal]:
    """Build {asset_category_nfkc_casefold: total_value} map."""
    result: dict[str, Decimal] = {}
    for h in holdings:
        if not h.asset_category:
            continue
        key = unicodedata.normalize("NFKC", h.asset_category).casefold().strip()
        result[key] = result.get(key, Decimal("0")) + (
            h.total_value if h.total_value else Decimal("0")
        )
    return result


def evaluate_all_checks(
    session: Session,
    *,
    household_id: UUID,
    as_of_date: date,
) -> GuardianEvaluationRun:
    """Evaluate all confirmed Guardian checks for a household."""
    return _evaluate_checks(session, household_id=household_id, as_of_date=as_of_date)


def evaluate_one_check(
    session: Session,
    *,
    check_id: UUID,
    household_id: UUID,
    as_of_date: date,
) -> GuardianEvaluationRun:
    """Evaluate a single confirmed Guardian check."""
    return _evaluate_checks(
        session, household_id=household_id, as_of_date=as_of_date,
        target_check_id=check_id,
    )


def _evaluate_checks(
    session: Session,
    *,
    household_id: UUID,
    as_of_date: date,
    target_check_id: Optional[UUID] = None,
) -> GuardianEvaluationRun:
    """Core evaluation logic — shared by evaluate-all and evaluate-one."""
    lock_household(session, household_id)

    # Read current published policy
    policy = get_current_published_policy(session, household_id)
    if policy is None:
        run = create_evaluation_run(
            session,
            run_id=uuid4(), household_id=household_id,
            status="skipped_no_published_policy",
            checks_evaluated=0, events_created=0,
            as_of_date=as_of_date,
            skip_reason="No published Policy version exists",
        )
        add_audit_event(
            session,
            id=uuid4(), household_id=household_id,
            actor="owner", action="guardian.evaluation.skipped",
            entity_type="guardian_evaluation_run", entity_id=str(run.id),
            metadata={
                "evaluation_run_id": str(run.id),
                "status": run.status,
                "skip_reason": run.skip_reason,
            },
        )
        return run

    # Read current portfolio snapshot
    snapshot = get_current_portfolio_snapshot(session, household_id)
    if snapshot is None:
        run = create_evaluation_run(
            session,
            run_id=uuid4(), household_id=household_id,
            status="skipped_no_portfolio_snapshot",
            checks_evaluated=0, events_created=0,
            as_of_date=as_of_date,
            skip_reason="No Portfolio Snapshot exists",
        )
        add_audit_event(
            session,
            id=uuid4(), household_id=household_id,
            actor="owner", action="guardian.evaluation.skipped",
            entity_type="guardian_evaluation_run", entity_id=str(run.id),
            metadata={
                "evaluation_run_id": str(run.id),
                "status": run.status,
                "skip_reason": run.skip_reason,
            },
        )
        return run

    holdings = get_snapshot_holdings(session, snapshot.id)
    total_value = _compute_total_value(holdings)
    if total_value == Decimal("0") or not has_any_holdings(session, snapshot.id):
        run = create_evaluation_run(
            session,
            run_id=uuid4(), household_id=household_id,
            status="skipped_zero_total_value",
            checks_evaluated=0, events_created=0,
            as_of_date=as_of_date,
            skip_reason="Portfolio Snapshot has zero total value",
        )
        add_audit_event(
            session,
            id=uuid4(), household_id=household_id,
            actor="owner", action="guardian.evaluation.skipped",
            entity_type="guardian_evaluation_run", entity_id=str(run.id),
            metadata={
                "evaluation_run_id": str(run.id),
                "status": run.status,
                "skip_reason": run.skip_reason,
            },
        )
        return run

    category_map = _build_category_map(holdings)

    # Determine which checks to evaluate
    if target_check_id is not None:
        confirmed = get_confirmed_version(session, target_check_id)
        if confirmed is None:
            # Not a confirmed version — check if a confirmed version exists
            c = get_latest_confirmed_version(session, target_check_id)
            if c is None:
                raise CheckNotFoundError(
                    f"No confirmed version for check {target_check_id}"
                )
            confirmed = c
        checks = [confirmed]
    else:
        checks = list(
            session.query(GuardianCheckConfirmed)
            .join(GuardianCheck)
            .filter(GuardianCheck.household_id == household_id)
            .all()
        )

    run_id = uuid4()
    events_created = 0
    all_events: list[GuardianEvent] = []

    # Evaluate each confirmed check
    for cc in checks:
        event = _evaluate_single_check(
            session, cc, policy, snapshot, holdings, category_map,
            total_value, as_of_date, run_id,
        )
        if event is not None:
            events_created += 1
            all_events.append(event)

    run = create_evaluation_run(
        session,
        run_id=run_id, household_id=household_id,
        status="completed",
        checks_evaluated=len(checks),
        events_created=events_created,
        as_of_date=as_of_date,
    )

    add_audit_event(
        session,
        id=uuid4(), household_id=household_id,
        actor="owner", action="guardian.evaluation.completed",
        entity_type="guardian_evaluation_run", entity_id=str(run_id),
        metadata={
            "evaluation_run_id": str(run_id),
            "checks_evaluated": len(checks),
            "events_created": events_created,
            "policy_version_id": str(policy.id),
            "portfolio_snapshot_id": str(snapshot.id),
        },
    )
    return run


def _evaluate_single_check(
    session: Session,
    cc: GuardianCheckConfirmed,
    policy: "InvestmentPolicyVersion",
    snapshot: "PortfolioSnapshot",
    holdings: Sequence[PortfolioSnapshotHolding],
    category_map: dict[str, Decimal],
    total_value: Decimal,
    as_of_date: date,
    run_id: UUID,
) -> Optional[GuardianEvent]:
    """Evaluate one confirmed check. Returns GuardianEvent if threshold exceeded."""
    if cc.check_type == "drift":
        return _evaluate_drift(
            session, cc, policy, snapshot,
            category_map, total_value, as_of_date, run_id,
        )
    elif cc.check_type == "category_exposure":
        return _evaluate_category_exposure(
            session, cc, policy, snapshot,
            category_map, total_value, as_of_date, run_id,
        )
    elif cc.check_type == "staleness":
        return _evaluate_staleness(
            session, cc, policy, snapshot, as_of_date, run_id,
        )
    return None


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


def _evaluate_drift(
    session: Session,
    cc: GuardianCheckConfirmed,
    policy: "InvestmentPolicyVersion",
    snapshot: "PortfolioSnapshot",
    category_map: dict[str, Decimal],
    total_value: Decimal,
    as_of_date: date,
    run_id: UUID,
) -> Optional[GuardianEvent]:
    """Drift: abs(actual_pp - target_pp) > threshold."""
    # Find Policy allocation matching target_category
    from apps.api.models import InvestmentPolicyVersionAllocation
    target_cat_norm = _norm(cc.target_category or "")
    policy_pct: Optional[Decimal] = None
    allocations = (
        session.query(InvestmentPolicyVersionAllocation)
        .filter(
            InvestmentPolicyVersionAllocation.version_id == policy.id,
        )
        .all()
    )
    for alloc in allocations:
        if _norm(alloc.asset_class_name) == target_cat_norm:
            policy_pct = alloc.target_percentage
            break

    if policy_pct is None:
        # Category not in Policy allocations — skip (no drift to measure)
        return None

    # Find Portfolio category
    holding_cat_norm = _norm(cc.target_holding_category or "")
    portfolio_val = category_map.get(holding_cat_norm, Decimal("0"))

    actual_pct: Decimal
    if total_value == Decimal("0"):
        actual_pct = Decimal("0")
    else:
        actual_pct = (
            portfolio_val / total_value * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    drift_pp = abs(actual_pct - policy_pct).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    if drift_pp <= cc.threshold_value:
        return None  # equal or below — no event

    # Threshold exceeded
    return _insert_drift_event(
        session, cc, policy, snapshot, drift_pp, as_of_date, run_id,
    )


def _insert_drift_event(
    session: Session,
    cc: GuardianCheckConfirmed,
    policy: "InvestmentPolicyVersion",
    snapshot: "PortfolioSnapshot",
    drift_pp: Decimal,
    as_of_date: date,
    run_id: UUID,
) -> Optional[GuardianEvent]:
    """Insert drift event with ON CONFLICT DO NOTHING (fingerprint dedup)."""
    household_id = cc.check.household_id
    try:
        event = GuardianEvent(
            id=uuid4(),
            evaluation_run_id=run_id,
            household_id=household_id,
            check_id=cc.check_id,
            check_version_id=cc.id,
            check_type="drift",
            policy_version_id=policy.id,
            portfolio_snapshot_id=snapshot.id,
            exceeded=True,
            drift_pp=drift_pp,
            as_of_date=as_of_date,
        )
        session.add(event)
        session.flush()
        return event
    except IntegrityError:
        session.rollback()
        return None


def _evaluate_category_exposure(
    session: Session,
    cc: GuardianCheckConfirmed,
    policy: "InvestmentPolicyVersion",
    snapshot: "PortfolioSnapshot",
    category_map: dict[str, Decimal],
    total_value: Decimal,
    as_of_date: date,
    run_id: UUID,
) -> Optional[GuardianEvent]:
    """Category exposure: category_pct > threshold."""
    holding_cat_norm = _norm(cc.target_holding_category or "")
    cat_value = category_map.get(holding_cat_norm, Decimal("0"))

    actual_pct: Decimal
    if total_value == Decimal("0"):
        actual_pct = Decimal("0")
    else:
        actual_pct = (
            cat_value / total_value * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    if actual_pct <= cc.threshold_value:
        return None

    event = GuardianEvent(
        id=uuid4(),
        evaluation_run_id=run_id,
        household_id=cc.check.household_id,
        check_id=cc.check_id,
        check_version_id=cc.id,
        check_type="category_exposure",
        policy_version_id=policy.id,
        portfolio_snapshot_id=snapshot.id,
        exceeded=True,
        exposure_pct=actual_pct,
        as_of_date=as_of_date,
    )
    try:
        session.add(event)
        session.flush()
        return event
    except IntegrityError:
        session.rollback()
        return None


def _evaluate_staleness(
    session: Session,
    cc: GuardianCheckConfirmed,
    policy: "InvestmentPolicyVersion",
    snapshot: "PortfolioSnapshot",
    as_of_date: date,
    run_id: UUID,
) -> Optional[GuardianEvent]:
    """Staleness: snapshot age in days > staleness_days threshold."""
    if snapshot.valuation_date is None:
        return None
    delta_days = (as_of_date - snapshot.valuation_date).days
    if delta_days <= cc.staleness_days:
        return None

    event = GuardianEvent(
        id=uuid4(),
        evaluation_run_id=run_id,
        household_id=cc.check.household_id,
        check_id=cc.check_id,
        check_version_id=cc.id,
        check_type="staleness",
        policy_version_id=policy.id,
        portfolio_snapshot_id=snapshot.id,
        exceeded=True,
        staleness_days_actual=delta_days,
        as_of_date=as_of_date,
    )
    try:
        session.add(event)
        session.flush()
        return event
    except IntegrityError:
        session.rollback()
        return None
