"""Sprint 007 Slice A — Restore verification service.

Safe restore: only to newly created _test databases.
Break-glass restore to production is NOT implemented here.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

RESTORE_DB_TEMPLATE = "compoundos_restore_test_{suffix}"
REQUIRED_TABLES = frozenset({
    "household_profiles", "audit_events",
    "investment_policies", "investment_policy_drafts",
    "investment_policy_versions", "investment_policy_allocations",
    "decisions", "decision_drafts", "decision_confirmed_snapshots",
    "decision_corrections", "portfolio_snapshots", "portfolio_holdings",
    "guardian_checks", "guardian_events",
    "job_definitions", "schedules", "runs", "attempts", "leases",
    "committee_sessions", "committee_evidence_items",
    "committee_reports", "committee_outcomes",
    "backup_records", "export_tasks",
})


# ═══════════════════════════════════════════════════════════════════════════


def restore_and_verify(
    backup_path: str,
    age_recipient: str,
    db_host: str = "127.0.0.1",
    db_user: str = "compoundos",
    db_password: str = "local-development-only",
    db_port: int = 5432,
) -> str | None:
    """Restore to disposable _test DB, verify schema. Returns error or None."""
    suffix = _suffix_from_path(backup_path)
    test_db = RESTORE_DB_TEMPLATE.format(suffix=suffix)

    # Enforce _test suffix — check after template substitution, not before
    if "_test" not in test_db or "restore_test" not in test_db:
        return f"Safety: restore target must contain '_test', got {test_db}"

    try:
        # Step 1: Create disposable test database
        _drop_if_exists(test_db, db_host, db_user, db_password, db_port)
        _create_db(test_db, db_host, db_user, db_password, db_port)

        # Step 2: Decrypt
        tmp_dump = Path(backup_path + ".restore.tmp")
        try:
            r = subprocess.run(
                ["age", "--decrypt", "-o", str(tmp_dump), backup_path],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                return f"Decrypt failed: {r.stderr[:200]}"

            # Step 3: Restore
            db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{test_db}"
            r2 = subprocess.run(
                ["pg_restore", "--dbname", db_url, "--no-owner", "--no-privileges",
                 "--single-transaction", str(tmp_dump)],
                capture_output=True, text=True, timeout=120,
            )
            if r2.returncode != 0:
                return f"pg_restore failed: {r2.stderr[:200]}"

            # Step 4: Verify schema
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema='public' AND table_type='BASE TABLE'"
                ))
                tables = {row[0] for row in result.fetchall()}
                missing = REQUIRED_TABLES - tables
                if missing:
                    return f"Missing tables: {missing}"

                # Check migration head
                head = conn.execute(text(
                    "SELECT version_num FROM alembic_version"
                )).scalar()
                if not head or not head.startswith("001"):
                    return f"Unexpected migration head: {head}"

            # Cleanup
            _drop_if_exists(test_db, db_host, db_user, db_password, db_port)
            return None
        finally:
            if tmp_dump.exists():
                tmp_dump.unlink()
    except Exception as e:
        # Clean up test db on failure
        try:
            _drop_if_exists(test_db, db_host, db_user, db_password, db_port)
        except Exception:
            pass
        return str(e)[:200]


# ═══════════════════════════════════════════════════════════════════════════
# Internal
# ═══════════════════════════════════════════════════════════════════════════


def _suffix_from_path(path: str) -> str:
    h = hashlib.sha256(path.encode()).hexdigest()[:8]
    return h


def _drop_if_exists(
    db_name: str,
    host: str, user: str, password: str, port: int,
) -> None:
    maint_url = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(maint_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(
            f"DROP DATABASE IF EXISTS \"{db_name}\""
        ))
    engine.dispose()


def _create_db(
    db_name: str,
    host: str, user: str, password: str, port: int,
) -> None:
    maint_url = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    engine = create_engine(maint_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE \"{db_name}\" OWNER \"{user}\""
        ))
    engine.dispose()
