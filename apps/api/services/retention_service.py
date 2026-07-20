"""Sprint 007 Slice A — Backup retention service.

7 daily + 4 weekly + 12 monthly. Last healthy backup never deleted.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from apps.api.models import BackupRecord


def apply_retention(session: Session) -> int:
    """Apply retention policy. Returns count of expired backups deleted."""
    completed = (
        session.query(BackupRecord)
        .filter(BackupRecord.status == "completed")
        .order_by(desc(BackupRecord.completed_at))
        .all()
    )

    if not completed:
        return 0

    # Never delete the last completed backup
    if len(completed) <= 1:
        _mark_all_locked_except_latest(session, completed)
        return 0

    # Compute retention windows
    now = datetime.now(timezone.utc)
    keep_ids: set[str] = set()

    # Daily: last 7 distinct days
    daily = _distinct_dates(completed, lambda t: t.date(), 7)
    keep_ids.update(daily)

    # Weekly: last 4 distinct ISO weeks
    weekly = _distinct_dates(
        completed,
        lambda t: (t.isocalendar().year, t.isocalendar().week),
        4,
    )
    keep_ids.update(weekly)

    # Monthly: last 12 distinct months
    monthly = _distinct_dates(completed, lambda t: (t.year, t.month), 12)
    keep_ids.update(monthly)

    # Lock: the single latest completed backup is always kept
    latest = completed[0]
    keep_ids.add(str(latest.id))
    latest.retention_category = "locked"

    # Delete
    deleted = 0
    for record in completed:
        if str(record.id) in keep_ids:
            if record.retention_category is None:
                record.retention_category = _compute_category(record, daily, weekly, monthly)
            continue
        # Safety: never delete if it's the last healthy backup
        if _is_last_healthy(session, record):
            record.retention_category = "locked"
            continue
        _delete_artifact(str(record.file_path))
        session.delete(record)
        deleted += 1

    session.commit()
    return deleted


# ═══════════════════════════════════════════════════════════════════════════
# Internal
# ═══════════════════════════════════════════════════════════════════════════


def _distinct_dates(
    records: list[BackupRecord],
    key_fn,
    limit: int,
) -> set[str]:
    seen: set = set()
    result: set[str] = set()
    for r in records:
        if r.completed_at is None:
            continue
        k = key_fn(r.completed_at)
        if k in seen:
            continue
        seen.add(k)
        result.add(str(r.id))
        if len(result) >= limit:
            break
    return result


def _is_last_healthy(session: Session, record: BackupRecord) -> bool:
    """Check if this is the last completed backup remaining."""
    count = (
        session.query(BackupRecord)
        .filter(
            BackupRecord.status == "completed",
            BackupRecord.id != record.id,
        )
        .count()
    )
    return count == 0


def _compute_category(
    record: BackupRecord,
    daily: set[str],
    weekly: set[str],
    monthly: set[str],
) -> str:
    rid = str(record.id)
    if rid in daily:
        return "daily"
    if rid in weekly:
        return "weekly"
    if rid in monthly:
        return "monthly"
    return "daily"


def _delete_artifact(file_path: str) -> None:
    try:
        os.unlink(file_path)
    except FileNotFoundError:
        pass


def _mark_all_locked_except_latest(
    session: Session,
    completed: list[BackupRecord],
) -> None:
    if not completed:
        return
    latest = completed[0]
    for r in completed:
        if r.id != latest.id:
            r.retention_category = "locked"
