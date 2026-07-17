"""Guardian service layer — check lifecycle + evaluation engine (Sprint 004 Slice B).

Architecture:
- Each public method opens ONE `session.begin()` transaction.
- All repository calls happen within that transaction.
- Pure evaluation functions (`guardian_evaluator`) have no DB access.
- No lazy relationships used after session closes.
- Response DTOs are built inside the transaction.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.guardian_schemas import canonicalize_name
from apps.api.services.guardian_evaluator import (
    CheckInput,
    EvaluationInput,
    EvaluationResult,
    PolicyAllocation,
    PortfolioHolding,
    SnapshotInfo,
    build_category_map,
    compute_total_value,
    evaluate_category_exposure,
    evaluate_drift,
    evaluate_staleness,
)

# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class HouseholdRequiredError(Exception):
    pass


class CheckNotFoundError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class DraftConflictError(Exception):
    pass


class NameConflictError(Exception):
    pass


class InvalidCheckTypeFieldsError(Exception):
    pass


class ConfirmRequiresDraftError(Exception):
    pass


# ---------------------------------------------------------------------------
# Per-type field validation (pure — no DB)
# ---------------------------------------------------------------------------


def _validate_draft_fields(
    check_type: str,
    threshold_value: Decimal,
    target_category: Optional[str],
    target_holding_category: Optional[str],
    staleness_days: Optional[int],
) -> None:
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


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


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
) -> dict:
    canonical = canonicalize_name(name)
    _validate_draft_fields(
        check_type, threshold_value, target_category,
        target_holding_category, staleness_days,
    )

    # Check uniqueness
    existing = session.execute(
        text(
            "SELECT id FROM guardian_checks"
            " WHERE household_id = :hid AND canonical_name = :cn"
        ),
        {"hid": household_id, "cn": canonical},
    ).fetchone()
    if existing:
        raise NameConflictError("A check with this name already exists")

    check_id = uuid4()
    session.execute(
        text(
            "INSERT INTO guardian_checks (id, household_id, name, canonical_name, check_type)"
            " VALUES (:id, :hid, :name, :cn, :ctype)"
        ),
        {"id": check_id, "hid": household_id, "name": name.strip(),
         "cn": canonical, "ctype": check_type},
    )
    session.execute(
        text(
            "INSERT INTO guardian_check_drafts"
            " (check_id, threshold_value, target_category, target_holding_category,"
            "  staleness_days, severity, notes, expected_revision)"
            " VALUES (:cid, :tv, :tc, :thc, :sd, :sev, :notes, 1)"
        ),
        {
            "cid": check_id,
            "tv": str(threshold_value),
            "tc": target_category,
            "thc": target_holding_category,
            "sd": staleness_days,
            "sev": severity,
            "notes": notes,
        },
    )
    _audit(session, household_id, "guardian.check.created", str(check_id),
           {"name": name.strip(), "check_type": check_type})

    result = _load_check_detail(session, check_id)
    return result


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
) -> dict:
    row = session.execute(
        text(
            "SELECT c.check_type, d.threshold_value, d.target_category,"
            " d.target_holding_category, d.staleness_days, d.severity, d.notes,"
            " d.expected_revision"
            " FROM guardian_checks c"
            " JOIN guardian_check_drafts d ON d.check_id = c.id"
            " WHERE c.id = :cid"
        ),
        {"cid": check_id},
    ).fetchone()
    if row is None:
        # Check might exist but no draft
        chk = session.execute(
            text("SELECT id FROM guardian_checks WHERE id = :cid"),
            {"cid": check_id},
        ).fetchone()
        if chk is None:
            raise CheckNotFoundError(f"Check {check_id} not found")
        raise DraftNotFoundError("No draft to update")

    (
        check_type, cur_tv, cur_tc, cur_thc, cur_sd, cur_sev, cur_notes, cur_rev,
    ) = row

    if expected_revision != cur_rev:
        raise DraftConflictError(
            f"Expected revision {expected_revision}, current is {cur_rev}"
        )

    new_tv = threshold_value if threshold_value is not None else Decimal(cur_tv)
    new_tc = target_category if target_category is not None else cur_tc
    new_thc = target_holding_category if target_holding_category is not None else cur_thc
    new_sd = staleness_days if staleness_days is not None else cur_sd
    new_sev = severity if severity is not None else cur_sev
    new_notes = notes if notes is not None else cur_notes

    _validate_draft_fields(check_type, new_tv, new_tc, new_thc, new_sd)

    new_rev = cur_rev + 1
    session.execute(
        text(
            "UPDATE guardian_check_drafts SET"
            " threshold_value = :tv, target_category = :tc,"
            " target_holding_category = :thc, staleness_days = :sd,"
            " severity = :sev, notes = :notes, expected_revision = :rev,"
            " updated_at = NOW()"
            " WHERE check_id = :cid"
        ),
        {
            "cid": check_id, "tv": str(new_tv), "tc": new_tc,
            "thc": new_thc, "sd": new_sd, "sev": new_sev,
            "notes": new_notes, "rev": new_rev,
        },
    )
    result = _load_check_detail(session, check_id)
    return result


def confirm_guardian_check(
    session: Session,
    *,
    check_id: UUID,
    expected_revision: int,
) -> dict:
    row = session.execute(
        text(
            "SELECT c.id, c.household_id, c.check_type, d.threshold_value,"
            " d.target_category, d.target_holding_category, d.staleness_days,"
            " d.severity, d.notes, d.expected_revision"
            " FROM guardian_checks c"
            " JOIN guardian_check_drafts d ON d.check_id = c.id"
            " WHERE c.id = :cid"
        ),
        {"cid": check_id},
    ).fetchone()
    if row is None:
        raise ConfirmRequiresDraftError("No draft to confirm")

    (
        cid, hid, ctype, tv, tc, thc, sd, sev, notes, rev,
    ) = row

    if rev != expected_revision:
        raise DraftConflictError(
            f"Expected revision {expected_revision}, draft is at {rev}"
        )

    tv_dec = Decimal(tv)
    _validate_draft_fields(ctype, tv_dec, tc, thc, sd)

    # Get next version number
    vrow = session.execute(
        text(
            "SELECT COALESCE(MAX(version_number), 0) + 1"
            " FROM guardian_check_confirmed WHERE check_id = :cid"
        ),
        {"cid": cid},
    ).fetchone()
    next_ver = vrow[0]

    ccid = uuid4()
    session.execute(
        text(
            "INSERT INTO guardian_check_confirmed"
            " (id, check_id, version_number, check_type, threshold_value,"
            "  target_category, target_holding_category, staleness_days, severity, notes)"
            " VALUES (:id, :cid, :ver, :ctype, :tv, :tc, :thc, :sd, :sev, :notes)"
        ),
        {
            "id": ccid, "cid": cid, "ver": next_ver, "ctype": ctype,
            "tv": str(tv_dec), "tc": tc, "thc": thc,
            "sd": sd, "sev": sev, "notes": notes,
        },
    )
    session.execute(
        text("UPDATE guardian_checks SET status = 'confirmed', updated_at = NOW() WHERE id = :cid"),
        {"cid": cid},
    )
    _audit(session, hid, "guardian.check.confirmed", str(cid),
           {"version_number": next_ver, "check_type": ctype})

    result = _load_check_detail(session, cid)
    return result


def discard_guardian_check(session: Session, check_id: UUID) -> None:
    row = session.execute(
        text(
            "SELECT c.id, c.household_id,"
            " EXISTS(SELECT 1 FROM guardian_check_confirmed WHERE check_id = c.id) AS has_confirmed"
            " FROM guardian_checks c WHERE c.id = :cid"
        ),
        {"cid": check_id},
    ).fetchone()
    if row is None:
        raise CheckNotFoundError(f"Check {check_id} not found")

    cid, hid, has_confirmed = row

    session.execute(
        text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"),
        {"cid": cid},
    )
    if has_confirmed:
        session.execute(
            text("UPDATE guardian_checks SET status = 'draft', updated_at = NOW() WHERE id = :cid"),
            {"cid": cid},
        )
        _audit(session, hid, "guardian.check.draft_discarded", str(cid),
               {"retained_confirmed": True})
    else:
        session.execute(
            text("DELETE FROM guardian_checks WHERE id = :cid"),
            {"cid": cid},
        )
        _audit(session, hid, "guardian.check.deleted", str(cid),
               {"had_confirmed": False})


# ---------------------------------------------------------------------------
# Evaluation engine — single transaction
# ---------------------------------------------------------------------------


def evaluate_all_checks(
    session: Session,
    *,
    household_id: UUID,
    as_of_date: date,
) -> dict:
    """Entry point: manual evaluate-all."""
    return _evaluate(session, household_id=household_id, as_of_date=as_of_date)


def evaluate_one_check(
    session: Session,
    *,
    check_id: UUID,
    household_id: UUID,
    as_of_date: date,
) -> dict:
    """Entry point: manual evaluate-one."""
    return _evaluate(session, household_id=household_id, as_of_date=as_of_date,
                     target_check_id=check_id)


def _evaluate(
    session: Session,
    *,
    household_id: UUID,
    as_of_date: date,
    target_check_id: Optional[UUID] = None,
) -> dict:
    """Single transaction: lock, load, compute, write, return."""
    # Lock household
    session.execute(
        text("SELECT id FROM household_profiles WHERE id = :hid FOR UPDATE"),
        {"hid": household_id},
    )

    run_id = uuid4()

    # --- Load Policy ---
    prow = session.execute(
        text(
            "SELECT pv.id, pv.version_number"
            " FROM investment_policy_versions pv"
            " JOIN investment_policies p ON p.id = pv.policy_id"
            " WHERE p.household_id = :hid"
            " AND pv.status = 'published' AND pv.superseded_at IS NULL"
        ),
        {"hid": household_id},
    ).fetchone()

    if prow is None:
        _insert_run(session, run_id, household_id, "skipped_no_published_policy",
                    0, 0, as_of_date, "No published Policy version exists")
        _audit_eval(session, household_id, run_id, "skipped",
                     "no_published_policy", 0, 0)
        return _load_eval_result(session, run_id)

    policy_version_id, policy_version_number = prow
    policy_version_id_str = str(policy_version_id)

    # --- Load Policy allocations ---
    arows = session.execute(
        text(
            "SELECT asset_class_name, normalized_asset_class_name, target_percentage"
            " FROM investment_policy_version_allocations WHERE version_id = :vid"
        ),
        {"vid": policy_version_id},
    ).fetchall()
    allocations = [
        PolicyAllocation(
            asset_class_name=r[0],
            normalized_name=r[1] or r[0],
            target_percentage=Decimal(str(r[2])),
        )
        for r in arows
    ]

    # --- Load Portfolio snapshot ---
    srow = session.execute(
        text(
            "SELECT ps.id, ps.version_number, ps.valuation_date"
            " FROM portfolio_snapshots ps"
            " JOIN portfolios p ON p.id = ps.portfolio_id"
            " WHERE p.household_id = :hid AND ps.status = 'current'"
        ),
        {"hid": household_id},
    ).fetchone()

    if srow is None:
        _insert_run(session, run_id, household_id, "skipped_no_portfolio_snapshot",
                    0, 0, as_of_date, "No Portfolio Snapshot exists")
        _audit_eval(session, household_id, run_id, "skipped",
                     "no_portfolio_snapshot", 0, 0)
        return _load_eval_result(session, run_id)

    snapshot_id, snapshot_version, snapshot_val_date = srow
    portfolio_snapshot_id_str = str(snapshot_id)

    # --- Load holdings ---
    hrows = session.execute(
        text(
            "SELECT asset_category, total_value"
            " FROM portfolio_snapshot_holdings WHERE snapshot_id = :sid"
        ),
        {"sid": snapshot_id},
    ).fetchall()

    holdings = [
        PortfolioHolding(asset_category=r[0], total_value=Decimal(str(r[1])))
        for r in hrows
    ]
    total_value = compute_total_value(holdings)

    if total_value == Decimal("0") or len(hrows) == 0:
        _insert_run(session, run_id, household_id, "skipped_zero_total_value",
                    0, 0, as_of_date, "Portfolio Snapshot has zero total value")
        _audit_eval(session, household_id, run_id, "skipped",
                     "zero_total_value", 0, 0)
        return _load_eval_result(session, run_id)

    category_map = build_category_map(holdings)

    # --- Load confirmed checks ---
    if target_check_id is not None:
        crows = session.execute(
            text(
                "SELECT cc.id, cc.check_id, cc.check_type, cc.threshold_value,"
                " cc.severity, cc.target_category, cc.target_holding_category,"
                " cc.staleness_days"
                " FROM guardian_check_confirmed cc"
                " JOIN guardian_checks gc ON gc.id = cc.check_id"
                " WHERE cc.check_id = :cid AND gc.household_id = :hid"
            ),
            {"cid": target_check_id, "hid": household_id},
        ).fetchall()
    else:
        crows = session.execute(
            text(
                "SELECT cc.id, cc.check_id, cc.check_type, cc.threshold_value,"
                " cc.severity, cc.target_category, cc.target_holding_category,"
                " cc.staleness_days"
                " FROM guardian_check_confirmed cc"
                " JOIN guardian_checks gc ON gc.id = cc.check_id"
                " WHERE gc.household_id = :hid"
            ),
            {"hid": household_id},
        ).fetchall()

    checks = [
        CheckInput(
            check_id=str(r[1]),
            check_version_id=str(r[0]),
            check_type=r[2],
            threshold_value=Decimal(str(r[3])),
            severity=r[4],
            target_category_norm=r[5],
            target_holding_category_norm=r[6],
            staleness_days=r[7],
        )
        for r in crows
    ]

    # --- Evaluate ---
    events_created = 0
    for chk in checks:
        evt_id = _evaluate_one_check(
            session, chk, allocations, category_map, total_value,
            snapshot_val_date, policy_version_id_str,
            portfolio_snapshot_id_str, as_of_date, run_id,
        )
        if evt_id is not None:
            events_created += 1

    _insert_run(
        session, run_id, household_id, "completed",
        len(checks), events_created, as_of_date, None,
    )
    _audit_eval(
        session, household_id, run_id, "completed", None,
        len(checks), events_created,
        policy_version_id=policy_version_id_str,
        policy_version_number=policy_version_number,
        snapshot_id=portfolio_snapshot_id_str,
        snapshot_version=snapshot_version,
    )

    result = _load_eval_result(session, run_id)
    return result


def _evaluate_one_check(
    session: Session,
    chk: CheckInput,
    allocations: Sequence[PolicyAllocation],
    category_map: dict[str, Decimal],
    total_value: Decimal,
    snapshot_val_date: date,
    policy_version_id_str: str,
    portfolio_snapshot_id_str: str,
    as_of_date: date,
    run_id: UUID,
) -> Optional[UUID]:
    """Evaluate one check. Returns event UUID if exceeded, None otherwise."""
    if chk.check_type == "drift":
        r = evaluate_drift(chk, allocations, category_map, total_value)
    elif chk.check_type == "category_exposure":
        r = evaluate_category_exposure(chk, category_map, total_value)
    elif chk.check_type == "staleness":
        r = evaluate_staleness(chk, snapshot_val_date, as_of_date)
    else:
        return None

    if not r.exceeded:
        return None

    return _insert_event(
        session, run_id, chk,
        policy_version_id=UUID(policy_version_id_str),
        portfolio_snapshot_id=UUID(portfolio_snapshot_id_str),
        as_of_date=as_of_date,
        result=r,
    )


# ---------------------------------------------------------------------------
# Repository helpers (in-service only)
# ---------------------------------------------------------------------------


def _get_household(session: Session) -> UUID:
    row = session.execute(
        text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    if row is None:
        raise HouseholdRequiredError("Household profile not found")
    return row[0]


def _audit(session: Session, hid: UUID, action: str, eid: str, meta: dict) -> None:
    session.execute(
        text(
            "INSERT INTO audit_events (id, household_id, actor, action,"
            " entity_type, entity_id, metadata, occurred_at)"
            " VALUES (:id, :hid, 'owner', :action, 'guardian_check', :eid,"
            " :meta::jsonb, NOW())"
        ),
        {"id": uuid4(), "hid": hid, "action": action, "eid": eid,
         "meta": json.dumps(meta)},
    )


def _audit_eval(
    session: Session, hid: UUID, run_id: UUID, status: str,
    skip_reason: Optional[str], checks: int, events: int,
    policy_version_id: Optional[str] = None,
    policy_version_number: Optional[int] = None,
    snapshot_id: Optional[str] = None,
    snapshot_version: Optional[int] = None,
) -> None:
    meta = {
        "evaluation_run_id": str(run_id),
        "checks_evaluated": checks,
        "events_created": events,
    }
    if status != "completed" and skip_reason:
        meta["status"] = status
        meta["skip_reason"] = skip_reason
    if policy_version_id:
        meta["policy_version_id"] = policy_version_id
        meta["policy_version_number"] = policy_version_number
    if snapshot_id:
        meta["portfolio_snapshot_id"] = snapshot_id
        meta["portfolio_snapshot_version"] = snapshot_version

    session.execute(
        text(
            "INSERT INTO audit_events (id, household_id, actor, action,"
            " entity_type, entity_id, metadata, occurred_at)"
            " VALUES (:id, :hid, 'owner', :action, 'guardian_evaluation_run', :eid,"
            " :meta::jsonb, NOW())"
        ),
        {
            "id": uuid4(), "hid": hid,
            "action": f"guardian.evaluation.{status}",
            "eid": str(run_id), "meta": json.dumps(meta),
        },
    )


def _insert_run(
    session: Session, run_id: UUID, hid: UUID, status: str,
    checks: int, events: int, as_of_date: date, skip_reason: Optional[str],
) -> None:
    session.execute(
        text(
            "INSERT INTO guardian_evaluation_runs"
            " (id, household_id, status, checks_evaluated, events_created,"
            "  as_of_date, skip_reason)"
            " VALUES (:id, :hid, :status, :checks, :events, :as_of, :skip)"
        ),
        {
            "id": run_id, "hid": hid, "status": status,
            "checks": checks, "events": events,
            "as_of": as_of_date, "skip": skip_reason,
        },
    )


def _insert_event(
    session: Session,
    run_id: UUID,
    chk: CheckInput,
    *,
    policy_version_id: UUID,
    portfolio_snapshot_id: UUID,
    as_of_date: date,
    result: EvaluationResult,
) -> Optional[UUID]:
    """INSERT ... ON CONFLICT DO NOTHING RETURNING id."""
    if chk.check_type in ("drift", "category_exposure"):
        conflict_cols = "check_version_id, policy_version_id, portfolio_snapshot_id"
        conflict_where = "check_type IN ('drift', 'category_exposure')"
    else:
        conflict_cols = "check_version_id, portfolio_snapshot_id, as_of_date"
        conflict_where = "check_type = 'staleness'"

    row = session.execute(
        text(
            "INSERT INTO guardian_events"
            " (id, evaluation_run_id, household_id, check_id, check_version_id,"
            "  check_type, policy_version_id, portfolio_snapshot_id,"
            "  exceeded, drift_pp, exposure_pct, staleness_days_actual, as_of_date)"
            " VALUES (:id, :run_id, :hid, :cid, :cvid,"
            "  :ctype, :pvid, :sid, TRUE,"
            "  :drift_pp, :exposure_pct, :staleness_days, :as_of)"
            f" ON CONFLICT ({conflict_cols}) WHERE {conflict_where} DO NOTHING"
            " RETURNING id"
        ),
        {
            "id": uuid4(),
            "run_id": run_id,
            "hid": UUID(chk.check_id),  # placeholder — get from DB
            "cid": UUID(chk.check_id),
            "cvid": UUID(chk.check_version_id),
            "ctype": chk.check_type,
            "pvid": policy_version_id,
            "sid": portfolio_snapshot_id,
            "drift_pp": str(result.drift_pp) if result.drift_pp else None,
            "exposure_pct": str(result.exposure_pct) if result.exposure_pct else None,
            "staleness_days": result.staleness_days_actual,
            "as_of": as_of_date,
        },
    ).fetchone()
    return row[0] if row else None


def _load_check_detail(session: Session, check_id: UUID) -> dict:
    """Build detail dict inside transaction."""
    crow = session.execute(
        text(
            "SELECT id, household_id, name, canonical_name, check_type, status,"
            " created_at, updated_at FROM guardian_checks WHERE id = :cid"
        ),
        {"cid": check_id},
    ).fetchone()
    if crow is None:
        raise CheckNotFoundError(f"Check {check_id} not found")

    drow = session.execute(
        text(
            "SELECT threshold_value, target_category, target_holding_category,"
            " staleness_days, severity, notes, expected_revision, updated_at"
            " FROM guardian_check_drafts WHERE check_id = :cid"
        ),
        {"cid": check_id},
    ).fetchone()

    lrow = session.execute(
        text(
            "SELECT id, check_id, version_number, check_type, threshold_value,"
            " target_category, target_holding_category, staleness_days, severity,"
            " notes, confirmed_at"
            " FROM guardian_check_confirmed WHERE check_id = :cid"
            " ORDER BY version_number DESC LIMIT 1"
        ),
        {"cid": check_id},
    ).fetchone()

    return {
        "identity": {
            "id": crow[0], "household_id": crow[1], "name": crow[2],
            "canonical_name": crow[3], "check_type": crow[4], "status": crow[5],
            "created_at": crow[6], "updated_at": crow[7],
        },
        "draft": {
            "threshold_value": str(drow[0]), "target_category": drow[1],
            "target_holding_category": drow[2], "staleness_days": drow[3],
            "severity": drow[4], "notes": drow[5],
            "expected_revision": drow[6], "updated_at": drow[7],
        } if drow else None,
        "latest_version": {
            "id": lrow[0], "check_id": lrow[1], "version_number": lrow[2],
            "check_type": lrow[3], "threshold_value": str(lrow[4]),
            "target_category": lrow[5], "target_holding_category": lrow[6],
            "staleness_days": lrow[7], "severity": lrow[8],
            "notes": lrow[9], "confirmed_at": lrow[10],
        } if lrow else None,
    }


def _load_eval_result(session: Session, run_id: UUID) -> dict:
    """Build evaluation result dict inside transaction."""
    rrow = session.execute(
        text(
            "SELECT id, household_id, status, skip_reason, checks_evaluated,"
            " events_created, as_of_date, created_at"
            " FROM guardian_evaluation_runs WHERE id = :rid"
        ),
        {"rid": run_id},
    ).fetchone()
    if rrow is None:
        raise CheckNotFoundError(f"Evaluation run {run_id} not found")

    erows = session.execute(
        text(
            "SELECT id, evaluation_run_id, check_id, check_version_id, check_type,"
            " policy_version_id, portfolio_snapshot_id, exceeded,"
            " drift_pp, exposure_pct, staleness_days_actual, as_of_date, detected_at"
            " FROM guardian_events WHERE evaluation_run_id = :rid"
        ),
        {"rid": run_id},
    ).fetchall()

    def _s(v):
        return str(v) if v is not None else None

    return {
        "evaluation_run": {
            "id": str(rrow[0]), "household_id": str(rrow[1]),
            "status": rrow[2], "skip_reason": rrow[3],
            "checks_evaluated": rrow[4], "events_created": rrow[5],
            "as_of_date": str(rrow[6]) if rrow[6] else None,
            "created_at": rrow[7],
        },
        "events": [
            {
                "id": str(e[0]), "evaluation_run_id": str(e[1]),
                "check_id": str(e[2]), "check_version_id": str(e[3]),
                "check_type": e[4], "policy_version_id": str(e[5]),
                "portfolio_snapshot_id": str(e[6]), "exceeded": e[7],
                "drift_pp": _s(e[8]), "exposure_pct": _s(e[9]),
                "staleness_days_actual": e[10],
                "as_of_date": str(e[11]) if e[11] else None,
                "detected_at": e[12],
            }
            for e in erows
        ],
    }
