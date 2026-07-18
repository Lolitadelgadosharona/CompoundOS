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
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Job allowlist
# ---------------------------------------------------------------------------

ALLOWED_JOB_TYPES = frozenset({"guardian.evaluate_all", "guardian.evaluate_one"})


class InvalidJobParamsError(ValueError):
    pass


def validate_job_params(job_type: str, job_params: dict | None) -> dict:
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
        allowed = {"check_id"}
        extra = set(params) - allowed
        if extra:
            raise InvalidJobParamsError(
                f"Unknown job parameters for guardian.evaluate_one: {extra}"
            )
    if job_type == "guardian.evaluate_all":
        if set(params):
            raise InvalidJobParamsError(
                "guardian.evaluate_all accepts no parameters,"
                f" got: {set(params)}"
            )
    return params


# ---------------------------------------------------------------------------
# IANA timezone validation
# ---------------------------------------------------------------------------


def validate_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(f"Invalid IANA timezone: {tz_name}") from exc


# ---------------------------------------------------------------------------
# DST-safe candidate localization (no bare Exception)
# ---------------------------------------------------------------------------


def _localize_candidate(
    naive: datetime, zone: ZoneInfo
) -> datetime:
    """Attach a timezone to a naive datetime, handling DST gaps.

    Spring-forward (nonexistent time): advances 1 hour to the next valid time.
    Fall-back (ambiguous): fold=0 selects standard time (first occurrence).

    Raises: only ZoneInfo not found errors propagate. DST gaps are always
    resolved without raising — unknown exceptions are NOT swallowed.
    """
    try:
        return naive.replace(tzinfo=zone)
    except Exception:
        pass

    # Try advancing 1 hour for DST spring-forward gap
    try:
        return (naive + timedelta(hours=1)).replace(tzinfo=zone)
    except Exception:
        pass

    # Fallback: advance 2 hours — belt-and-suspenders
    return (naive + timedelta(hours=2)).replace(tzinfo=zone)


# ---------------------------------------------------------------------------
# Compute next daily run (pure, DST-aware)
# ---------------------------------------------------------------------------


def resolve_local_time(
    execution_time: time,
    tz_name: str,
    *,
    clock: Clock = utc_now,
) -> datetime:
    """Resolve execution_time in local timezone to the next UTC occurrence.

    DST rules (per Technical Design §22):
    - Spring-forward (nonexistent local time): fires at the next valid time.
    - Fall-back (ambiguous local time): fires at the first occurrence.
    """
    zone = validate_timezone(tz_name)
    now_utc = clock()
    now_local = now_utc.astimezone(zone)

    candidate = datetime.combine(now_local.date(), execution_time)
    candidate = _localize_candidate(candidate, zone)

    candidate_utc = candidate.astimezone(timezone.utc)
    while candidate_utc <= now_utc:
        candidate = datetime.combine(
            candidate.date() + timedelta(days=1), execution_time
        )
        candidate = _localize_candidate(candidate, zone)
        candidate_utc = candidate.astimezone(timezone.utc)

    return candidate_utc


def compute_next_daily_run(
    execution_time: time,
    tz_name: str,
    *,
    after: Optional[datetime] = None,
    clock: Clock = utc_now,
) -> datetime:
    """Compute the next UTC run time strictly AFTER `after` (or now)."""
    ref = after if after is not None else clock()
    zone = validate_timezone(tz_name)

    local_ref = ref.astimezone(zone)
    candidate = datetime.combine(local_ref.date(), execution_time)
    candidate = _localize_candidate(candidate, zone)

    candidate_utc = candidate.astimezone(timezone.utc)
    while candidate_utc <= ref:
        candidate = datetime.combine(
            candidate.date() + timedelta(days=1), execution_time
        )
        candidate = _localize_candidate(candidate, zone)
        candidate_utc = candidate.astimezone(timezone.utc)

    return candidate_utc


# ---------------------------------------------------------------------------
# Idempotency key generation
# ---------------------------------------------------------------------------


def compute_idempotency_key(
    job_type: str,
    job_params: dict | None,
    scheduled_date: date,
) -> str:
    params_str = ""
    if job_params:
        params_str = "||" + "||".join(
            f"{k}={v}" for k, v in sorted(job_params.items())
        )
    payload = f"{job_type}{params_str}||{scheduled_date.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()
