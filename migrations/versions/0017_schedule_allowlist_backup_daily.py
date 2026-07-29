"""Sprint 008 Slice C — Expand job_type allowlist for backup.daily.

Revision ID: 0017_schedule_allowlist_backup_daily
Revises: 0016_notification_integrity
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0017_schedule_allowlist_backup_daily"
down_revision: Union[str, None] = "0016_notification_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALLOWLIST_UPGRADE_FN = r"""
CREATE OR REPLACE FUNCTION public.fn_job_definition_allowlist()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.job_type NOT IN (
        'guardian.evaluate_all', 'guardian.evaluate_one', 'backup.daily'
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_job_type_not_allowed',
            DETAIL = 'Job type ' || NEW.job_type || ' is not in the approved allowlist.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()

ALLOWLIST_DOWNGRADE_FN = r"""
CREATE OR REPLACE FUNCTION public.fn_job_definition_allowlist()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.job_type NOT IN ('guardian.evaluate_all', 'guardian.evaluate_one') THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_job_type_not_allowed',
            DETAIL = 'Job type ' || NEW.job_type || ' is not in the approved allowlist.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()


def upgrade() -> None:
    op.execute(ALLOWLIST_UPGRADE_FN)


def downgrade() -> None:
    op.execute(ALLOWLIST_DOWNGRADE_FN)
