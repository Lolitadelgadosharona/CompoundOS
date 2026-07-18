"""Pure scheduling functions — no database, no ORM, injectable clock.

Sprint 005 Slice B — Data Orchestration Worker + Backend API.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---------------------------------------------------------------------------
# Clock injection
# ---------------------------------------------------------------------------

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Production clock — UTC now."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Job allowlist
# ---------------------------------------------------------------------------

ALLOWED_JOB_TYPES = frozenset({"guardian.evaluate_all", "guardian.evaluate_one"})

# ---------------------------------------------------------------------------
# Job parameter validation (pure)
# ---------------------------------------------------------------------------


class InvalidJobParamsError(ValueError):
    pass


def validate_job_params(job_type: str, job_params: dict | None) -> dict:
    """Validate and normalise job parameters per the allowlist.

    Returns the validated params dict (empty dict if None).
    Raises InvalidJobParamsError for unknown types or invalid params.
    """
    if job_type not in ALLOWED_JOB_TYPES:
        raise InvalidJobParamsError(
            f"Job type '{job_type}' is not in the approved allowlist."
        )

    params = dict(job_params) if job_params else {}

    if job_type == "guardian.evaluate_one":
        check_id = params.get("check_id")
        if not check_id:
            raise InvalidJobParamsError(
                "guardian.evaluate_one requires 'check_id' in job_params."
            )
        # Only allow check_id
        allowed = {"check_id"}
        extra = set(params) - allowed
        if extra:
            raise InvalidJobParamsError(
                f"Unknown job parameters for guardian.evaluate_one: {extra}"
            )

    if job_type == "guardian.evaluate_all":
        # No required params; reject any unknown params
        if set(params) - set():
            raise InvalidJobParamsError(
                f"guardian.evaluate_all accepts no job parameters, got: {set(params)}"
            )

    return params


# ---------------------------------------------------------------------------
# IANA timezone validation (pure)
# ---------------------------------------------------------------------------


def validate_timezone(tz_name: str) -> ZoneInfo:
    """Validate an IANA timezone name. Returns the ZoneInfo or raises ValueError."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(f"Invalid IANA timezone: {tz_name}") from exc


# ---------------------------------------------------------------------------
# Compute next daily run (pure, DST-aware)
# ---------------------------------------------------------------------------


def _as_utc(dt: datetime, zone: ZoneInfo, now: Callable[[], datetime]) -> datetime:
    """Convert a naive local datetime to a UTC datetime using the given zone."""
    localized = dt.replace(tzinfo=zone)
    return localized.astimezone(timezone.utc)


def resolve_local_time(
    execution_time: time,
    tz_name: str,
    *,
    clock: Clock = utc_now,
) -> datetime:
    """Resolve execution_time in local timezone to the next UTC occurrence.

    DST rules (per Technical Design §22):
    - Spring-forward (nonexistent local time): fires at the next valid time after the gap.
    - Fall-back (ambiguous local time): fires at the first occurrence (standard time).
    """
    zone = validate_timezone(tz_name)
    now_utc = clock()
    now_local = now_utc.astimezone(zone)

    # Build candidate: today at execution_time in the local zone
    candidate = datetime.combine(now_local.date(), execution_time)

    # Handle DST transitions
    try:
        candidate = candidate.replace(tzinfo=zone)
    except Exception:
        # Nonexistent time (spring-forward gap) — advance 1 hour
        candidate = (candidate + timedelta(hours=1)).replace(tzinfo=zone)

    # If candidate is ambiguous (fall-back), fold=0 selects the first occurrence
    # (standard time). fold=0 is the default, so no special handling needed.

    # If candidate has passed, advance to next day
    candidate_utc = candidate.astimezone(timezone.utc)
    while candidate_utc <= now_utc:
        candidate = datetime.combine(
            candidate.date() + timedelta(days=1), execution_time
        )
        try:
            candidate = candidate.replace(tzinfo=zone)
        except Exception:
            candidate = (candidate + timedelta(hours=1)).replace(tzinfo=zone)
        candidate_utc = candidate.astimezone(timezone.utc)

    return candidate_utc


def compute_next_daily_run(
    execution_time: time,
    tz_name: str,
    *,
    after: Optional[datetime] = None,
    clock: Clock = utc_now,
) -> datetime:
    """Compute the next UTC run time strictly AFTER `after` (or now).

    Returns a timezone-aware UTC datetime.
    """
    ref = after if after is not None else clock()
    zone = validate_timezone(tz_name)

    # Start from ref date in local zone
    local_ref = ref.astimezone(zone)
    candidate = datetime.combine(local_ref.date(), execution_time)

    try:
        candidate = candidate.replace(tzinfo=zone)
    except Exception:
        candidate = (candidate + timedelta(hours=1)).replace(tzinfo=zone)

    candidate_utc = candidate.astimezone(timezone.utc)

    # Advance until strictly after ref
    while candidate_utc <= ref:
        candidate = datetime.combine(
            candidate.date() + timedelta(days=1), execution_time
        )
        try:
            candidate = candidate.replace(tzinfo=zone)
        except Exception:
            candidate = (candidate + timedelta(hours=1)).replace(tzinfo=zone)
        candidate_utc = candidate.astimezone(timezone.utc)

    return candidate_utc


# ---------------------------------------------------------------------------
# Idempotency key generation (pure)
# ---------------------------------------------------------------------------


def compute_idempotency_key(
    job_type: str,
    job_params: dict | None,
    scheduled_date: date,
) -> str:
    """Deterministic idempotency key per Technical Design §8.

    Formula: SHA256(job_type || canonical_job_params || scheduled_date).
    """
    params_str = ""
    if job_params:
        params_str = "||" + "||".join(
            f"{k}={v}" for k, v in sorted(job_params.items())
        )
    payload = f"{job_type}{params_str}||{scheduled_date.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()
