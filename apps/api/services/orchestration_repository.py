"""Worker repository — direct PostgreSQL operations for claim/lease/finalize.

Sprint 005 Slice B — all operations are atomic, single-statement, token-gated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Constants (per Technical Design: TTL 60s, heartbeat 15s, max runtime 5m)
# ---------------------------------------------------------------------------

LEASE_TTL_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 15
MAX_RUNTIME_SECONDS = 300
GRACEFUL_SHUTDOWN_SECONDS = 30


def _utc_now() -> datetime:
    """Production clock."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Claim due work — atomic SKIP LOCKED
# ---------------------------------------------------------------------------


def claim_due_schedules(
    session: Session,
    *,
    clock: Any = None,
) -> list[dict]:
    """Atomically claim due schedules using FOR UPDATE SKIP LOCKED.

    Returns list of dicts with schedule_id, job_definition_id, job_type,
    job_params, household_id, next_run_at.
    """
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    rows = session.execute(
        text(
            "SELECT s.id AS schedule_id, s.job_definition_id,"
            " jd.job_type, jd.job_params, jd.household_id,"
            " s.next_run_at, s.execution_time, s.timezone"
            " FROM schedules s"
            " JOIN job_definitions jd ON jd.id = s.job_definition_id"
            " WHERE s.enabled = TRUE AND s.next_run_at <= :now"
            " ORDER BY s.next_run_at"
            " FOR UPDATE OF s SKIP LOCKED"
        ),
        {"now": now},
    ).mappings().all()

    results = []
    for row in rows:
        results.append({
            "schedule_id": str(row["schedule_id"]),
            "job_definition_id": str(row["job_definition_id"]),
            "job_type": row["job_type"],
            "job_params": row["job_params"],
            "household_id": str(row["household_id"]),
            "next_run_at": row["next_run_at"],
            "execution_time": row["execution_time"],
            "timezone": row["timezone"],
        })
    return results


# ---------------------------------------------------------------------------
# Run creation (atomic, idempotent)
# ---------------------------------------------------------------------------


def create_run(
    session: Session,
    *,
    job_definition_id: str,
    schedule_id: str | None,
    idempotency_key: str,
    status: str,
    triggered_by: str,
    scheduled_at: datetime,
    household_id: str,
    clock: Any = None,
) -> str:
    """Create a new Run. Returns the run_id as string.

    Raises IntegrityError on duplicate idempotency_key (already claimed).
    """
    (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    run_id = uuid4()
    session.execute(
        text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key,"
            " status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik, :st, :tb, :sa, :hid)"
        ),
        {
            "id": run_id,
            "jid": job_definition_id,
            "sid": schedule_id,
            "ik": idempotency_key,
            "st": status,
            "tb": triggered_by,
            "sa": scheduled_at,
            "hid": household_id,
        },
    )
    return str(run_id)


def advance_next_run_at(
    session: Session,
    schedule_id: str,
    new_next_run_at: datetime,
    *,
    clock: Any = None,
) -> int:
    """Atomically advance next_run_at for a schedule. Returns rowcount."""
    result = session.execute(
        text("UPDATE schedules SET next_run_at = :nr WHERE id = :sid"),
        {"nr": new_next_run_at, "sid": schedule_id},
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Attempt creation
# ---------------------------------------------------------------------------


def create_attempt(
    session: Session,
    *,
    run_id: str,
    attempt_number: int,
    status: str = "pending",
    clock: Any = None,
) -> str:
    """Create a new Attempt. Returns the attempt_id as string."""
    (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    aid = uuid4()
    session.execute(
        text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, :num, :st)"
        ),
        {"id": aid, "rid": run_id, "num": attempt_number, "st": status},
    )
    return str(aid)


# ---------------------------------------------------------------------------
# Attempt status updates
# ---------------------------------------------------------------------------


def start_attempt(
    session: Session,
    attempt_id: str,
    *,
    clock: Any = None,
) -> int:
    """Mark attempt as running. Returns rowcount."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(
            "UPDATE attempts SET status = 'running', started_at = :now"
            " WHERE id = :id"
        ),
        {"id": attempt_id, "now": now},
    )
    return result.rowcount


def complete_attempt(
    session: Session,
    attempt_id: str,
    status: str,
    *,
    error_message: str | None = None,
    clock: Any = None,
) -> int:
    """Mark attempt as succeeded/failed/aborted. Returns rowcount."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(
            "UPDATE attempts SET status = :st, completed_at = :now,"
            " error_message = :err WHERE id = :id"
        ),
        {"id": attempt_id, "st": status, "now": now, "err": error_message},
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Run status updates
# ---------------------------------------------------------------------------


def start_run(
    session: Session,
    run_id: str,
    *,
    clock: Any = None,
) -> int:
    """Mark run as running. Returns rowcount."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(
            "UPDATE runs SET status = 'running', started_at = :now"
            " WHERE id = :id"
        ),
        {"id": run_id, "now": now},
    )
    return result.rowcount


def complete_run(
    session: Session,
    run_id: str,
    status: str,
    *,
    clock: Any = None,
) -> int:
    """Mark run as completed/failed/aborted. Returns rowcount."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(
            "UPDATE runs SET status = :st, completed_at = :now"
            " WHERE id = :id"
        ),
        {"id": run_id, "st": status, "now": now},
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Lease acquisition (first create)
# ---------------------------------------------------------------------------


def acquire_lease(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    clock: Any = None,
) -> dict:
    """Acquire the initial lease for a run.

    Returns dict with lease_id, fencing_token.
    The trigger auto-assigns fencing_token = 1.
    """
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    expires = now + timedelta(seconds=LEASE_TTL_SECONDS)
    lid = uuid4()

    session.execute(
        text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, :wid, :exp, :now, :now)"
        ),
        {"id": lid, "rid": run_id, "wid": worker_id, "exp": expires, "now": now},
    )
    session.flush()

    row = session.execute(
        text("SELECT id, fencing_token FROM leases WHERE id = :id"),
        {"id": lid},
    ).fetchone()

    return {"lease_id": str(row[0]), "fencing_token": row[1]}


# ---------------------------------------------------------------------------
# Lease takeover (atomic, per migration 0011 contract)
# ---------------------------------------------------------------------------


_TAKEOVER_SQL = (
    "UPDATE leases SET"
    " fencing_token = fencing_token + 1,"
    " worker_id = :wid,"
    " acquired_at = :as_of,"
    " heartbeat_at = :as_of,"
    " expires_at = :new_exp,"
    " released_at = NULL"
    " WHERE id = :lid"
    " AND fencing_token = :base"
    " AND expires_at <= :as_of"
    " RETURNING fencing_token"
)


def takeover_lease(
    session: Session,
    *,
    lease_id: str,
    worker_id: str,
    base_token: int,
    clock: Any = None,
) -> int | None:
    """Atomically takeover an expired lease.

    Returns new fencing_token on success, None if takeover failed
    (unexpired, stale token, or already taken).
    """
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    new_exp = now + timedelta(seconds=LEASE_TTL_SECONDS)

    result = session.execute(
        text(_TAKEOVER_SQL),
        {
            "lid": lease_id,
            "wid": worker_id,
            "base": base_token,
            "as_of": now,
            "new_exp": new_exp,
        },
    )
    row = result.fetchone()
    if row is None:
        return None
    return row[0]


# ---------------------------------------------------------------------------
# Heartbeat (atomic, token-gated, expiry-checked)
# ---------------------------------------------------------------------------


_HEARTBEAT_SQL = (
    "UPDATE leases SET heartbeat_at = :as_of"
    " WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    " AND released_at IS NULL AND expires_at > :as_of"
)


def heartbeat_lease(
    session: Session,
    *,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    clock: Any = None,
) -> int:
    """Atomically heartbeat a lease. Returns rowcount (0 = stale/expired)."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(_HEARTBEAT_SQL),
        {"lid": lease_id, "wid": worker_id, "token": fencing_token, "as_of": now},
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Finalize (atomic, token-gated, expiry-checked, run+attempt in one)
# ---------------------------------------------------------------------------


_FINALIZE_RUN_SQL = (
    "UPDATE runs SET status = :st, completed_at = :as_of"
    " WHERE id = :rid AND EXISTS ("
    "  SELECT 1 FROM leases"
    "  WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    "  AND released_at IS NULL AND expires_at > :as_of"
    " )"
)


def finalize_run(
    session: Session,
    *,
    run_id: str,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    status: str,
    clock: Any = None,
) -> int:
    """Atomically finalize a run. Returns rowcount (0 = stale/expired)."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(_FINALIZE_RUN_SQL),
        {
            "rid": run_id,
            "lid": lease_id,
            "wid": worker_id,
            "token": fencing_token,
            "st": status,
            "as_of": now,
        },
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Release lease
# ---------------------------------------------------------------------------


def release_lease(
    session: Session,
    *,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    clock: Any = None,
) -> int:
    """Release a lease. Returns rowcount."""
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    result = session.execute(
        text(
            "UPDATE leases SET released_at = :now"
            " WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
        ),
        {"lid": lease_id, "wid": worker_id, "token": fencing_token, "now": now},
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Recover stale runs (for crash recovery)
# ---------------------------------------------------------------------------


def recover_stale_runs(
    session: Session,
    *,
    clock: Any = None,
) -> list[dict]:
    """Find runs stuck in 'running' with expired leases.

    Returns list of dicts with run_id, lease_id, worker_id, fencing_token.
    """
    now = (clock or _utc_now)() if callable(clock) else clock or _utc_now()
    rows = session.execute(
        text(
            "SELECT r.id AS run_id, l.id AS lease_id,"
            " l.worker_id, l.fencing_token"
            " FROM runs r"
            " JOIN leases l ON l.run_id = r.id"
            " WHERE r.status = 'running'"
            " AND l.released_at IS NULL"
            " AND l.expires_at <= :now"
        ),
        {"now": now},
    ).mappings().all()

    return [
        {
            "run_id": str(r["run_id"]),
            "lease_id": str(r["lease_id"]),
            "worker_id": r["worker_id"],
            "fencing_token": r["fencing_token"],
        }
        for r in rows
    ]
