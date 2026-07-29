"""Sprint 008 Slice C — Daily schedule seed.

Ensures Guardian and Backup daily schedules exist, default disabled.
Idempotent — safe to call on every startup.
"""

from __future__ import annotations

import logging
from datetime import time

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DAILY_SCHEDULES = [
    {
        "job_type": "guardian.evaluate_all",
        "execution_time": time(9, 0),
        "timezone": "UTC",
        "label": "Guardian daily evaluation",
    },
    {
        "job_type": "backup.daily",
        "execution_time": time(2, 0),
        "timezone": "UTC",
        "label": "Backup daily",
    },
]


def seed_daily_schedules(session: Session) -> None:
    """Ensure daily schedules exist. Default disabled. Idempotent.
    
    Safe to call when no household exists — simply returns early.
    """
    from uuid import uuid4

    # Guard: no household → nothing to seed
    existing = session.execute(
        text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    if existing is None:
        return

    for spec in DAILY_SCHEDULES:
        job_type = spec["job_type"]
        existing_jd = session.execute(
            text(
                "SELECT id FROM job_definitions"
                " WHERE job_type = :jt LIMIT 1"
            ),
            {"jt": job_type},
        ).fetchone()

        if existing_jd is not None:
            # Job definition exists — check for schedule
            jd_id = existing_jd[0]
            existing_schedule = session.execute(
                text(
                    "SELECT id FROM schedules"
                    " WHERE job_definition_id = :jd_id LIMIT 1"
                ),
                {"jd_id": jd_id},
            ).fetchone()
            if existing_schedule is not None:
                continue  # Already exists — nothing to do
        else:
            # Create job definition
            jd_id = uuid4()
            session.execute(
                text(
                    "INSERT INTO job_definitions"
                    " (id, household_id, job_type, job_params)"
                    " VALUES (:id,"
                    " (SELECT id FROM household_profiles LIMIT 1),"
                    " :jt, '{}'::jsonb)"
                ),
                {"id": jd_id, "jt": job_type},
            )

        # Create schedule — default disabled, Owner must enable
        sid = uuid4()
        session.execute(
            text(
                "INSERT INTO schedules"
                " (id, job_definition_id, execution_time, timezone,"
                " enabled, next_run_at)"
                " VALUES (:id, :jd_id, :et, :tz, false, NOW())"
            ),
            {
                "id": sid,
                "jd_id": jd_id,
                "et": spec["execution_time"],
                "tz": spec["timezone"],
            },
        )
        logger.info(
            "Seeded daily schedule '%s' (default disabled)",
            spec["label"],
        )

    session.commit()
