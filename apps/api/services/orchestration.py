"""Automation service layer — Sprint 005 Slice B."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.automation_schemas import (
    JobDefinitionCreate,
    ManualTriggerRequest,
    ScheduleCreate,
    ScheduleUpdate,
)
from apps.api.services.orchestration_repository import (
    create_run as _repo_create_run,
)
from apps.api.services.orchestration_scheduling import (
    compute_idempotency_key,
    resolve_local_time,
)

# ── Job Definitions ──


def create_job_definition(
    session: Session,
    household_id: str,
    payload: JobDefinitionCreate,
) -> dict:
    """Create a job definition and return its data."""
    jid = uuid4()
    datetime.now()
    session.execute(
        text(
            "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
            " VALUES (:id, :hid, :jt, :jp::jsonb)"
        ),
        {
            "id": jid,
            "hid": household_id,
            "jt": payload.job_type,
            "jp": str(payload.job_params).replace("'", '"'),
        },
    )
    row = session.execute(
        text("SELECT * FROM job_definitions WHERE id = :id"), {"id": jid}
    ).mappings().fetchone()
    return dict(row)


def get_job_definition(session: Session, job_id: str) -> dict | None:
    row = session.execute(
        text("SELECT * FROM job_definitions WHERE id = :id"), {"id": job_id}
    ).mappings().fetchone()
    return dict(row) if row else None


def list_job_definitions(session: Session, household_id: str) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT * FROM job_definitions WHERE household_id = :hid"
            " ORDER BY created_at DESC"
        ),
        {"hid": household_id},
    ).mappings().all()
    return [dict(r) for r in rows]


# ── Schedules ──


def create_schedule(
    session: Session,
    household_id: str,
    payload: ScheduleCreate,
) -> dict:
    """Create job definition + schedule atomically."""
    # Create job definition
    jid = uuid4()
    datetime.now()
    session.execute(
        text(
            "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
            " VALUES (:id, :hid, :jt, '{}'::jsonb)"
        ),
        {"id": jid, "hid": household_id, "jt": payload.job_type},
    )

    # Compute initial next_run_at
    next_run = resolve_local_time(payload.execution_time, payload.timezone)

    # Create schedule (disabled by default)
    sid = uuid4()
    session.execute(
        text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at)"
            " VALUES (:id, :jid, :et, :tz, :nr)"
        ),
        {
            "id": sid,
            "jid": jid,
            "et": payload.execution_time,
            "tz": payload.timezone,
            "nr": next_run,
        },
    )

    # Return combined response
    row = session.execute(
        text(
            "SELECT s.*, jd.job_type, jd.job_params"
            " FROM schedules s"
            " JOIN job_definitions jd ON jd.id = s.job_definition_id"
            " WHERE s.id = :id"
        ),
        {"id": sid},
    ).mappings().fetchone()
    return dict(row)


def get_schedule(session: Session, schedule_id: str) -> dict | None:
    row = session.execute(
        text(
            "SELECT s.*, jd.job_type, jd.job_params"
            " FROM schedules s"
            " JOIN job_definitions jd ON jd.id = s.job_definition_id"
            " WHERE s.id = :id"
        ),
        {"id": schedule_id},
    ).mappings().fetchone()
    return dict(row) if row else None


def list_schedules(session: Session, household_id: str) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT s.*, jd.job_type, jd.job_params"
            " FROM schedules s"
            " JOIN job_definitions jd ON jd.id = s.job_definition_id"
            " WHERE jd.household_id = :hid"
            " ORDER BY s.created_at DESC"
        ),
        {"hid": household_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def update_schedule(
    session: Session,
    schedule_id: str,
    payload: ScheduleUpdate,
) -> dict | None:
    """Update schedule fields. Recomputes next_run_at if time/tz changes."""
    updates = []
    params: dict = {"id": schedule_id}
    now = datetime.now()

    if payload.execution_time is not None:
        updates.append("execution_time = :et")
        params["et"] = payload.execution_time
    if payload.timezone is not None:
        updates.append("timezone = :tz")
        params["tz"] = payload.timezone
    if payload.enabled is not None:
        updates.append("enabled = :en")
        params["en"] = payload.enabled

    if updates:
        updates.append("updated_at = :now")
        params["now"] = now

        # If time or timezone changed, recompute next_run_at
        if payload.execution_time is not None or payload.timezone is not None:
            row = session.execute(
                text("SELECT execution_time, timezone FROM schedules WHERE id = :id"),
                {"id": schedule_id},
            ).fetchone()
            if row:
                et = payload.execution_time or row[0]
                tz = payload.timezone or row[1]
                new_next = resolve_local_time(et, tz)
                updates.append("next_run_at = :nr")
                params["nr"] = new_next

        session.execute(
            text(
                f"UPDATE schedules SET {', '.join(updates)} WHERE id = :id"
            ),
            params,
        )

    return get_schedule(session, schedule_id)


def delete_schedule(session: Session, schedule_id: str) -> bool:
    result = session.execute(
        text("DELETE FROM schedules WHERE id = :id"), {"id": schedule_id}
    )
    return result.rowcount > 0


# ── Runs ──


def list_runs(
    session: Session,
    household_id: str,
    *,
    job_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    base = (
        "SELECT r.* FROM runs r"
        " WHERE r.household_id = :hid"
    )
    params: dict = {"hid": household_id, "limit": limit, "offset": offset}
    if job_type:
        base += (
            " AND EXISTS (SELECT 1 FROM job_definitions jd"
            " WHERE jd.id = r.job_definition_id AND jd.job_type = :jt)"
        )
        params["jt"] = job_type
    base += " ORDER BY r.scheduled_at DESC LIMIT :limit OFFSET :offset"
    rows = session.execute(text(base), params).mappings().all()
    return [dict(r) for r in rows]


def get_run_detail(session: Session, run_id: str) -> dict | None:
    row = session.execute(
        text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}
    ).mappings().fetchone()
    if not row:
        return None
    result = dict(row)
    attempts = session.execute(
        text(
            "SELECT * FROM attempts WHERE run_id = :rid"
            " ORDER BY attempt_number"
        ),
        {"rid": run_id},
    ).mappings().all()
    result["attempts"] = [dict(a) for a in attempts]
    return result


def manual_trigger_run(
    session: Session,
    household_id: str,
    payload: ManualTriggerRequest,
) -> dict:
    """Manually trigger a run for a job definition."""
    jid = str(payload.job_definition_id)

    # Verify job definition exists and belongs to household
    job = session.execute(
        text(
            "SELECT * FROM job_definitions"
            " WHERE id = :id AND household_id = :hid"
        ),
        {"id": jid, "hid": household_id},
    ).mappings().fetchone()
    if not job:
        raise ValueError("Job definition not found or not owned by household")

    now = datetime.now()
    ikey = compute_idempotency_key(
        job["job_type"], job["job_params"], now.date()
    )

    run_id = _repo_create_run(
        session,
        job_definition_id=jid,
        schedule_id=None,
        idempotency_key=ikey,
        status="pending",
        triggered_by="manual",
        scheduled_at=now,
        household_id=household_id,
    )

    row = session.execute(
        text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}
    ).mappings().fetchone()
    return dict(row)


# ── Worker status ──


def get_worker_status(session: Session) -> dict:
    """Read-only worker/database heartbeat endpoint."""
    workers = session.execute(
        text(
            "SELECT COUNT(DISTINCT worker_id) FROM leases"
            " WHERE released_at IS NULL AND expires_at > NOW()"
        )
    ).scalar() or 0

    active_leases = session.execute(
        text(
            "SELECT COUNT(*) FROM leases"
            " WHERE released_at IS NULL AND expires_at > NOW()"
        )
    ).scalar() or 0

    running = session.execute(
        text("SELECT COUNT(*) FROM runs WHERE status = 'running'")
    ).scalar() or 0

    return {
        "worker_count": workers,
        "active_leases": active_leases,
        "running_runs": running,
    }
