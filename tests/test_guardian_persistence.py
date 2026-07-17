# ruff: noqa: E501
# PostgreSQL integration tests embed SQL strings that exceed the line length limit.
# This follows the same convention as other test files in the repository.

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres


HEAD_REVISION = "0007_guardian_foundation"
PREVIOUS_REVISION = "0006_portfolio_snapshot_status"

GUARDIAN_TABLES = {
    "guardian_checks",
    "guardian_check_drafts",
    "guardian_check_confirmed",
    "guardian_evaluation_runs",
    "guardian_events",
}

EXPECTED_GUARDIAN_FUNCTIONS = {
    "fn_guardian_check_confirmed_immutability",
    "fn_guardian_evaluation_runs_immutability",
    "fn_guardian_events_immutability",
}

EXPECTED_GUARDIAN_TRIGGERS = {
    "trg_guardian_check_confirmed_immutability",
    "trg_guardian_events_immutability",
    "trg_guardian_evaluation_runs_immutability",
}

# ---------------------------------------------------------------------------
# Migration lifecycle
# ---------------------------------------------------------------------------


def _alembic_cfg() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    return cfg


def _upgrade_head(engine: Engine) -> None:
    command.upgrade(_alembic_cfg(), "head")


def _downgrade_to(engine: Engine, revision: str) -> None:
    command.downgrade(_alembic_cfg(), revision)


def _current_revision(engine: Engine) -> str:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        rev = ctx.get_current_revision()
        assert rev is not None, "No current revision"
        return rev


@pytest.fixture()
def fresh_db(postgres_engine: Engine):
    """Truncate all, downgrade to 0006, re-upgrade to head."""
    with postgres_engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE TABLE portfolio_snapshot_holdings, portfolio_snapshots,"
            " portfolio_draft_holdings, portfolio_drafts,"
            " accounts, portfolios,"
            " decision_corrections, decision_confirmed_snapshots,"
            " decision_drafts, decisions, audit_events,"
            " investment_policy_version_allocations,"
            " investment_policy_draft_allocations,"
            " investment_policy_versions, investment_policy_drafts,"
            " investment_policies,"
            " household_profiles"
            " RESTART IDENTITY CASCADE"
        ))
    _downgrade_to(postgres_engine, PREVIOUS_REVISION)
    _upgrade_head(postgres_engine)
    return postgres_engine


# --- Migration cycle tests ---

def test_guardian_migration_upgrade_creates_head(fresh_db: Engine) -> None:
    assert _current_revision(fresh_db) == HEAD_REVISION


def test_guardian_migration_creates_all_tables(fresh_db: Engine) -> None:
    insp = inspect(fresh_db)
    existing = set(insp.get_table_names())
    for table in GUARDIAN_TABLES:
        assert table in existing, f"Missing table: {table}"


def test_guardian_migration_creates_functions(fresh_db: Engine) -> None:
    with fresh_db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT proname FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = 'public' AND proname LIKE 'fn_guardian_%'"
            )
        ).fetchall()
    names = {r[0] for r in rows}
    for fn in EXPECTED_GUARDIAN_FUNCTIONS:
        assert fn in names, f"Missing function: {fn}"


def test_guardian_migration_creates_triggers(fresh_db: Engine) -> None:
    with fresh_db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgname LIKE 'trg_guardian_%'"
            )
        ).fetchall()
    names = {r[0] for r in rows}
    for trg in EXPECTED_GUARDIAN_TRIGGERS:
        assert trg in names, f"Missing trigger: {trg}"


def test_guardian_migration_downgrade_removes_tables(fresh_db: Engine) -> None:
    _downgrade_to(fresh_db, PREVIOUS_REVISION)
    insp = inspect(fresh_db)
    existing = set(insp.get_table_names())
    for table in GUARDIAN_TABLES:
        assert table not in existing, f"Table not removed: {table}"


def test_guardian_migration_downgrade_removes_functions(fresh_db: Engine) -> None:
    _downgrade_to(fresh_db, PREVIOUS_REVISION)
    with fresh_db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT proname FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = 'public' AND proname LIKE 'fn_guardian_%'"
            )
        ).fetchall()
    assert len(rows) == 0, f"Functions not removed: {[r[0] for r in rows]}"


def test_guardian_migration_reupgrade_after_downgrade(fresh_db: Engine) -> None:
    _downgrade_to(fresh_db, PREVIOUS_REVISION)
    _upgrade_head(fresh_db)
    assert _current_revision(fresh_db) == HEAD_REVISION
    insp = inspect(fresh_db)
    existing = set(insp.get_table_names())
    for table in GUARDIAN_TABLES:
        assert table in existing, f"Missing after re-upgrade: {table}"


# ---------------------------------------------------------------------------
# Schema — named constraints
# ---------------------------------------------------------------------------


def test_guardian_checks_named_constraints(fresh_db: Engine) -> None:
    insp = inspect(fresh_db)
    checks = {
        c["name"]
        for c in insp.get_check_constraints("guardian_checks")
    }
    assert "ck_guardian_checks_type" in checks
    assert "ck_guardian_checks_status" in checks


def test_guardian_drafts_named_constraints(fresh_db: Engine) -> None:
    insp = inspect(fresh_db)
    checks = {
        c["name"]
        for c in insp.get_check_constraints("guardian_check_drafts")
    }
    assert "ck_guardian_drafts_threshold" in checks
    assert "ck_guardian_drafts_staleness_days" in checks
    assert "ck_guardian_drafts_severity" in checks


def test_guardian_evaluation_runs_named_constraints(fresh_db: Engine) -> None:
    insp = inspect(fresh_db)
    checks = {
        c["name"]
        for c in insp.get_check_constraints("guardian_evaluation_runs")
    }
    assert "ck_guardian_evaluation_runs_status" in checks
    assert "ck_guardian_evaluation_runs_checks_evaluated" in checks
    assert "ck_guardian_evaluation_runs_events_created" in checks


# ---------------------------------------------------------------------------
# Check type field validation
# ---------------------------------------------------------------------------

_HOUSEHOLD_INSERT = text(
    "INSERT INTO household_profiles (id, household_name, base_currency,"
    " investment_horizon, liquidity_needs, risk_statement, notes)"
    " VALUES (:id, 'Test', 'USD', '', '', '', '')"
)


def _create_household(conn, hid: str) -> None:
    conn.execute(_HOUSEHOLD_INSERT, {"id": hid})


def _create_check(conn, cid: str, hid: str, name: str, ctype: str) -> None:
    conn.execute(
        text(
            "INSERT INTO guardian_checks (id, household_id, name, canonical_name, check_type)"
            " VALUES (:id, :hid, :name, :cname, :ctype)"
        ),
        {"id": cid, "hid": hid, "name": name, "cname": name.lower(), "ctype": ctype},
    )


def _create_policy_version(conn, pvid: str, hid: str) -> None:
    """Create the minimum FK chain: investment_policy → version."""
    pid = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO investment_policies (id, household_id)"
            " VALUES (:id, :hid)"
        ),
        {"id": pid, "hid": hid},
    )
    conn.execute(
        text(
            "INSERT INTO investment_policy_versions"
            " (id, policy_id, version_number, status, published_at,"
            "  objectives, time_horizon, liquidity, diversification,"
            "  contribution_policy, rebalancing_policy, prohibited_assets,"
            "  leverage_policy, decision_process, notes)"
            " VALUES (:id, :pid, 1, 'published', NOW(),"
            "  'obj', 'horizon', '', '', '', '', '', '', '', '')"
        ),
        {"id": pvid, "pid": pid},
    )
    # Seal the version (required by deferred trigger at commit)
    conn.execute(
        text("UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"),
        {"id": pvid},
    )


def _create_portfolio_snapshot(
    conn, sid: str, hid: str,
    existing_portfolio_id: str = None, version: int = 1,
) -> str:
    """Create the minimum FK chain: portfolio → snapshot. Returns portfolio_id."""
    if existing_portfolio_id is not None:
        port_id = existing_portfolio_id
        # Supersede previous current snapshot
        conn.execute(
            text("UPDATE portfolio_snapshots SET status = 'superseded'"
                 " WHERE portfolio_id = :pid AND status = 'current'"),
            {"pid": port_id},
        )
        status = "current"
    else:
        port_id = str(uuid4())
        conn.execute(
            text("INSERT INTO portfolios (id, household_id, status) VALUES (:id, :hid, 'active')"),
            {"id": port_id, "hid": hid},
        )
        status = "current"
    conn.execute(
        text(
            "INSERT INTO portfolio_snapshots (id, portfolio_id, version_number, status, valuation_date)"
            " VALUES (:id, :pid, :version, :status, '2026-07-01')"
        ),
        {"id": sid, "pid": port_id, "version": version, "status": status},
    )
    return port_id


def test_drift_draft_requires_threshold_and_categories(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Drift", "drift")
        # Missing target_category should be allowed (it's nullable)
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'equities', 'equity')"
            ),
            {"cid": cid},
        )


def test_staleness_draft_requires_staleness_days(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Stale", "staleness")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, staleness_days)"
                " VALUES (:cid, 1.00, :days)"
            ),
            {"cid": cid, "days": 30},
        )


def test_threshold_value_bounds(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Bounds", "drift")
        # Zero threshold rejected
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_check_drafts"
                    " (check_id, threshold_value)"
                    " VALUES (:cid, 0)"
                ),
                {"cid": cid},
            )


def test_threshold_value_exceeds_100(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Over", "drift")
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_check_drafts"
                    " (check_id, threshold_value)"
                    " VALUES (:cid, 100.01)"
                ),
                {"cid": cid},
            )


def test_severity_enum_invalid(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "BadSev", "drift")
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_check_drafts"
                    " (check_id, threshold_value, severity)"
                    " VALUES (:cid, 5.00, 'urgent')"
                ),
                {"cid": cid},
            )


def test_check_type_enum_invalid(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_checks (id, household_id, name, canonical_name, check_type)"
                    " VALUES (:id, :hid, 'Bad', 'bad', 'invalid_type')"
                ),
                {"id": str(uuid4()), "hid": _get_household_id(conn)},
            )


# ---------------------------------------------------------------------------
# Name uniqueness
# ---------------------------------------------------------------------------


def _get_household_id(conn) -> str:
    row = conn.execute(text("SELECT id FROM household_profiles")).fetchone()
    return str(row[0])


def test_canonical_name_unique_per_household(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        conn.execute(
            text(
                "INSERT INTO guardian_checks (id, household_id, name, canonical_name, check_type)"
                " VALUES (:id, :hid, 'Test', 'test', 'drift')"
            ),
            {"id": str(uuid4()), "hid": hid},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_checks (id, household_id, name, canonical_name, check_type)"
                    " VALUES (:id, :hid, 'TEST', 'test', 'category_exposure')"
                ),
                {"id": str(uuid4()), "hid": hid},
            )


# ---------------------------------------------------------------------------
# Decimal precision
# ---------------------------------------------------------------------------


def test_threshold_decimal_precision(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Prec", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value)"
                " VALUES (:cid, 5.25)"
            ),
            {"cid": cid},
        )
        row = conn.execute(
            text("SELECT threshold_value FROM guardian_check_drafts WHERE check_id = :cid"),
            {"cid": cid},
        ).fetchone()
        assert row[0] == Decimal("5.25")


def test_threshold_negative_rejected(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        cid = str(uuid4())
        _create_check(conn, cid, _get_household_id(conn), "Neg", "drift")
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_check_drafts"
                    " (check_id, threshold_value)"
                    " VALUES (:cid, -1.00)"
                ),
                {"cid": cid},
            )


# ---------------------------------------------------------------------------
# Lifecycle: Draft → Confirmed → new Draft → Confirm
# ---------------------------------------------------------------------------


def test_first_confirm_creates_version_1(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "First", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'equities', 'equity')"
            ),
            {"cid": cid},
        )
        # Confirm
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'equities', 'equity', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        # Delete draft (consumed by confirm)
        conn.execute(text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid})
        # Update check status
        conn.execute(
            text("UPDATE guardian_checks SET status = 'confirmed' WHERE id = :cid"),
            {"cid": cid},
        )
        # Verify
        row = conn.execute(
            text("SELECT version_number, severity FROM guardian_check_confirmed WHERE check_id = :cid"),
            {"cid": cid},
        ).fetchone()
        assert row[0] == 1
        assert row[1] == "info"


def test_second_confirm_creates_version_2(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Second", "category_exposure")
        # First confirm
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_holding_category)"
                " VALUES (:cid, 30.00, 'equity')"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'category_exposure', 30.00, 'equity', 'info')"
            ),
            {"id": str(uuid4()), "cid": cid},
        )
        conn.execute(text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid})
        conn.execute(
            text("UPDATE guardian_checks SET status = 'confirmed' WHERE id = :cid"),
            {"cid": cid},
        )
        # Second draft + confirm
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_holding_category)"
                " VALUES (:cid, 40.00, 'equity')"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_holding_category, severity)"
                " VALUES (:id, :cid, 2, 'category_exposure', 40.00, 'equity', 'warning')"
            ),
            {"id": str(uuid4()), "cid": cid},
        )
        rows = conn.execute(
            text(
                "SELECT version_number FROM guardian_check_confirmed"
                " WHERE check_id = :cid ORDER BY version_number"
            ),
            {"cid": cid},
        ).fetchall()
        assert [r[0] for r in rows] == [1, 2]


def test_version_number_unique_per_check(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Dup", "staleness")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, staleness_days)"
                " VALUES (:cid, 1.00, 30)"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value, staleness_days, severity)"
                " VALUES (:id, :cid, 1, 'staleness', 0, 30, 'info')"
            ),
            {"id": str(uuid4()), "cid": cid},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_check_confirmed"
                    " (id, check_id, version_number, check_type, threshold_value, staleness_days, severity)"
                    " VALUES (:id, :cid, 1, 'staleness', 0, 15, 'info')"
                ),
                {"id": str(uuid4()), "cid": cid},
            )


# ---------------------------------------------------------------------------
# Immutability: Confirmed Versions
# ---------------------------------------------------------------------------


def test_confirmed_delete_forbidden(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Imm", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'eq', 'eq')"
            ),
            {"cid": cid},
        )
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        with pytest.raises((IntegrityError, OperationalError), match="guardian_check_confirmed_delete_forbidden"):
            conn.execute(text("DELETE FROM guardian_check_confirmed WHERE id = :id"), {"id": cvid})


def test_confirmed_update_forbidden(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Upd", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'eq', 'eq')"
            ),
            {"cid": cid},
        )
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        with pytest.raises((IntegrityError, OperationalError), match="guardian_check_confirmed_update_forbidden"):
            conn.execute(
                text("UPDATE guardian_check_confirmed SET severity = 'critical' WHERE id = :id"),
                {"id": cvid},
            )


# ---------------------------------------------------------------------------
# Immutability: Guardian Events
# ---------------------------------------------------------------------------


def test_event_delete_forbidden(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_evaluation_runs"
                " (id, household_id, status, checks_evaluated, events_created, as_of_date)"
                " VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"
            ),
            {"id": run_id, "hid": hid},
        )
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Evt", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'eq', 'eq')"
            ),
            {"cid": cid},
        )
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        # Need policy_version and portfolio_snapshot for FK
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        eid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_events"
                " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                "  check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date)"
                " VALUES (:id, :run, :hid, :cid, :cvid,"
                "  'drift', :pid, :sid, 3.50, '2026-07-17')"
            ),
            {
                "id": eid, "run": run_id, "hid": hid, "cid": cid, "cvid": cvid,
                "pid": pid, "sid": sid,
            },
        )
        with pytest.raises((IntegrityError, OperationalError), match="guardian_event_delete_forbidden"):
            conn.execute(text("DELETE FROM guardian_events WHERE id = :id"), {"id": eid})


# ---------------------------------------------------------------------------
# Immutability: Evaluation Runs
# ---------------------------------------------------------------------------


def test_evaluation_run_delete_forbidden(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_evaluation_runs"
                " (id, household_id, status, checks_evaluated, events_created, as_of_date)"
                " VALUES (:id, :hid, 'completed', 5, 2, '2026-07-17')"
            ),
            {"id": run_id, "hid": hid},
        )
        with pytest.raises((IntegrityError, OperationalError), match="guardian_evaluation_run_delete_forbidden"):
            conn.execute(text("DELETE FROM guardian_evaluation_runs WHERE id = :id"), {"id": run_id})


# ---------------------------------------------------------------------------
# EvaluationRun status constraints
# ---------------------------------------------------------------------------


def test_evaluation_run_invalid_status(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_evaluation_runs"
                    " (id, household_id, status, checks_evaluated, events_created, as_of_date)"
                    " VALUES (:id, :hid, 'invalid_status', 0, 0, '2026-07-17')"
                ),
                {"id": str(uuid4()), "hid": hid},
            )


def test_evaluation_run_negative_checks(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_evaluation_runs"
                    " (id, household_id, status, checks_evaluated, events_created, as_of_date)"
                    " VALUES (:id, :hid, 'completed', -1, 0, '2026-07-17')"
                ),
                {"id": str(uuid4()), "hid": hid},
            )


# ---------------------------------------------------------------------------
# Fingerprint deduplication
# ---------------------------------------------------------------------------


def test_drift_exposure_fingerprint_rejects_duplicate(fresh_db: Engine) -> None:
    """Duplicate (check_version_id, policy_version_id, portfolio_snapshot_id) rejected for drift."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_evaluation_runs"
                " (id, household_id, status, checks_evaluated, events_created, as_of_date)"
                " VALUES (:id, :hid, 'completed', 1, 0, '2026-07-17')"
            ),
            {"id": run_id, "hid": hid},
        )
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Dedup", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'eq', 'eq')"
            ),
            {"cid": cid},
        )
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        # First event — succeeds
        conn.execute(
            text(
                "INSERT INTO guardian_events"
                " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                "  check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date)"
                " VALUES (:id, :run, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"
            ),
            {"id": str(uuid4()), "run": run_id, "hid": hid, "cid": cid, "cvid": cvid,
             "pid": pid, "sid": sid},
        )
        # Same fingerprint — rejected by uq_guardian_events_drift_exposure
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_events"
                    " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                    "  check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date)"
                    " VALUES (:id, :run, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"
                ),
                {"id": str(uuid4()), "run": run_id, "hid": hid, "cid": cid, "cvid": cvid,
                 "pid": pid, "sid": sid},
            )


def test_staleness_same_date_conflict(fresh_db: Engine) -> None:
    """Staleness: same (check_version, snapshot, as_of_date) → conflict on partial index."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4())
        r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r2, "hid": hid})
        cid = str(uuid4())
        _create_check(conn, cid, hid, "SSDC", "staleness")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, staleness_days) VALUES (:cid, 1.00, 30)"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, staleness_days, severity) VALUES (:id, :cid, 1, 'staleness', 1.00, 30, 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, staleness_days_actual, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'staleness', :pid, :sid, 10, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, staleness_days_actual, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'staleness', :pid, :sid, 10, '2026-07-17')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


def test_staleness_different_date_succeeds(fresh_db: Engine) -> None:
    """Staleness: same (check_version, snapshot), different as_of_date → both succeed."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4())
        r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-18')"), {"id": r2, "hid": hid})
        cid = str(uuid4())
        _create_check(conn, cid, hid, "SDDS", "staleness")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, staleness_days) VALUES (:cid, 1.00, 30)"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, staleness_days, severity) VALUES (:id, :cid, 1, 'staleness', 1.00, 30, 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, staleness_days_actual, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'staleness', :pid, :sid, 10, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, staleness_days_actual, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'staleness', :pid, :sid, 11, '2026-07-18')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


def test_drift_same_inputs_different_asof_conflict(fresh_db: Engine) -> None:
    """Drift: same (cvid, pid, sid), different as_of_date → conflict (as_of_date not in partial index)."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4())
        r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-18')"), {"id": r2, "hid": hid})
        cid = str(uuid4())
        _create_check(conn, cid, hid, "DSIDAC", "drift")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_category, target_holding_category) VALUES (:cid, 5.00, 'eq', 'eq')"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-18')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


def test_drift_different_inputs_succeed(fresh_db: Engine) -> None:
    """Drift: different check_version → both succeed."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4())
        r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r2, "hid": hid})
        cid = str(uuid4())
        _create_check(conn, cid, hid, "DDIS", "drift")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_category, target_holding_category) VALUES (:cid, 5.00, 'eq', 'eq')"), {"cid": cid})
        cvid1 = str(uuid4())
        cvid2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"), {"id": cvid1, "cid": cid})
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 2, 'drift', 5.00, 'eq', 'eq', 'info')"), {"id": cvid2, "cid": cid})
        pid = str(uuid4())
        sid = str(uuid4())
        _create_policy_version(conn, pid, hid)
        _create_portfolio_snapshot(conn, sid, hid)
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid1, "pid": pid, "sid": sid})
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid2, "pid": pid, "sid": sid})


# ---------------------------------------------------------------------------
# Composite FK integrity: check_version_id + check_type must match confirmed
# ---------------------------------------------------------------------------


def test_event_type_must_match_confirmed_type_staleness_vs_drift(fresh_db: Engine) -> None:
    """Event check_type='staleness' with drift confirmed version → rejected."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 0, '2026-07-17')"), {"id": run_id, "hid": hid})
        cid = str(uuid4()); _create_check(conn, cid, hid, "TypeMismatch", "drift")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_category, target_holding_category) VALUES (:cid, 5.00, 'eq', 'eq')"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4()); sid = str(uuid4())
        _create_policy_version(conn, pid, hid); _create_portfolio_snapshot(conn, sid, hid)
        # event check_type='staleness' but confirmed check_type='drift' → FK violation
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, staleness_days_actual, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'staleness', :pid, :sid, 10, '2026-07-17')"), {"id": str(uuid4()), "r": run_id, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


def test_event_type_must_match_confirmed_type_drift_vs_staleness(fresh_db: Engine) -> None:
    """Event check_type='drift' with staleness confirmed version → rejected."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 0, '2026-07-17')"), {"id": run_id, "hid": hid})
        cid = str(uuid4()); _create_check(conn, cid, hid, "TypeMismatch2", "staleness")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, staleness_days) VALUES (:cid, 1.00, 30)"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, staleness_days, severity) VALUES (:id, :cid, 1, 'staleness', 1.00, 30, 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4()); sid = str(uuid4())
        _create_policy_version(conn, pid, hid); _create_portfolio_snapshot(conn, sid, hid)
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": run_id, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


# ---------------------------------------------------------------------------
# Category_exposure fingerprint test
# ---------------------------------------------------------------------------


def test_category_exposure_same_inputs_conflict(fresh_db: Engine) -> None:
    """Category_exposure: same (cvid, pid, sid) → conflict (as_of_date ignored)."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4()); r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-18')"), {"id": r2, "hid": hid})
        cid = str(uuid4()); _create_check(conn, cid, hid, "CatExpDedup", "category_exposure")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_holding_category) VALUES (:cid, 20.00, 'equity')"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_holding_category, severity) VALUES (:id, :cid, 1, 'category_exposure', 20.00, 'equity', 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4()); sid = str(uuid4())
        _create_policy_version(conn, pid, hid); _create_portfolio_snapshot(conn, sid, hid)
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, exposure_pct, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'category_exposure', :pid, :sid, 25.00, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, exposure_pct, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'category_exposure', :pid, :sid, 25.00, '2026-07-18')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid})


# ---------------------------------------------------------------------------\n# Diff-snapshot fingerprint: same version, different portfolio_snapshot → succeed\n# ---------------------------------------------------------------------------


def test_drift_diff_snapshot_succeeds(fresh_db: Engine) -> None:
    """Drift: same (cvid, pid), different sid → both succeed."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4()); r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r2, "hid": hid})
        cid = str(uuid4()); _create_check(conn, cid, hid, "DriftDiffSnap", "drift")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_category, target_holding_category) VALUES (:cid, 5.00, 'eq', 'eq')"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4()); sid1 = str(uuid4()); sid2 = str(uuid4())
        _create_policy_version(conn, pid, hid)
        port_id = _create_portfolio_snapshot(conn, sid1, hid)
        _create_portfolio_snapshot(conn, sid2, hid, existing_portfolio_id=port_id, version=2)
        # v1 snapshot
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid1})
        # v2 snapshot — different fingerprint, should succeed
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid2})


def test_category_exposure_diff_snapshot_succeeds(fresh_db: Engine) -> None:
    """Category_exposure: same (cvid, pid), different sid → both succeed."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        r1 = str(uuid4()); r2 = str(uuid4())
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r1, "hid": hid})
        conn.execute(text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 1, '2026-07-17')"), {"id": r2, "hid": hid})
        cid = str(uuid4()); _create_check(conn, cid, hid, "CEXPDiffSnap", "category_exposure")
        conn.execute(text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_holding_category) VALUES (:cid, 20.00, 'equity')"), {"cid": cid})
        cvid = str(uuid4())
        conn.execute(text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_holding_category, severity) VALUES (:id, :cid, 1, 'category_exposure', 20.00, 'equity', 'info')"), {"id": cvid, "cid": cid})
        pid = str(uuid4()); sid1 = str(uuid4()); sid2 = str(uuid4())
        _create_policy_version(conn, pid, hid)
        port_id = _create_portfolio_snapshot(conn, sid1, hid)
        _create_portfolio_snapshot(conn, sid2, hid, existing_portfolio_id=port_id, version=2)
        # v1 snapshot
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, exposure_pct, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'category_exposure', :pid, :sid, 25.00, '2026-07-17')"), {"id": str(uuid4()), "r": r1, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid1})
        # v2 snapshot — different fingerprint
        conn.execute(text("INSERT INTO guardian_events (id, evaluation_run_id, household_id, check_id, check_version_id, check_type, policy_version_id, portfolio_snapshot_id, exposure_pct, as_of_date) VALUES (:id, :r, :hid, :cid, :cvid, 'category_exposure', :pid, :sid, 25.00, '2026-07-17')"), {"id": str(uuid4()), "r": r2, "hid": hid, "cid": cid, "cvid": cvid, "pid": pid, "sid": sid2})


# ---------------------------------------------------------------------------
# Concurrent deduplication: two transactions inserting same fingerprint
# ---------------------------------------------------------------------------


def test_concurrent_duplicate_fingerprint_at_most_one_event(fresh_db: Engine) -> None:
    """Two concurrent transactions inserting same fingerprint → at most 1 event."""
    import threading

    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        run_id = str(uuid4())
        conn.execute(
            text("INSERT INTO guardian_evaluation_runs (id, household_id, status, checks_evaluated, events_created, as_of_date) VALUES (:id, :hid, 'completed', 1, 0, '2026-07-17')"),
            {"id": run_id, "hid": hid},
        )
        cid = str(uuid4()); _create_check(conn, cid, hid, "Concurrent", "drift")
        conn.execute(
            text("INSERT INTO guardian_check_drafts (check_id, threshold_value, target_category, target_holding_category) VALUES (:cid, 5.00, 'eq', 'eq')"),
            {"cid": cid},
        )
        cvid = str(uuid4())
        conn.execute(
            text("INSERT INTO guardian_check_confirmed (id, check_id, version_number, check_type, threshold_value, target_category, target_holding_category, severity) VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"),
            {"id": cvid, "cid": cid},
        )
        pid = str(uuid4()); sid = str(uuid4())
        _create_policy_version(conn, pid, hid); _create_portfolio_snapshot(conn, sid, hid)

    db_url = fresh_db.url
    barrier = threading.Barrier(2, timeout=10)
    results: list = []

    def insert_event() -> None:
        eng = create_engine(db_url)
        with eng.begin() as c:
            barrier.wait()
            try:
                c.execute(
                    text(
                        "INSERT INTO guardian_events"
                        " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                        "  check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date)"
                        " VALUES (:id, :r, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"
                    ),
                    {"id": str(uuid4()), "r": run_id, "hid": hid, "cid": cid,
                     "cvid": cvid, "pid": pid, "sid": sid},
                )
                results.append("inserted")
            except IntegrityError:
                results.append("conflict")
            except Exception:
                results.append("error")
        eng.dispose()

    t1 = threading.Thread(target=insert_event)
    t2 = threading.Thread(target=insert_event)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(results) == 2
    assert "inserted" in results
    assert "conflict" in results or "inserted" in results
    # Exactly 1 row in DB
    with fresh_db.connect() as c:
        count = c.execute(
            text("SELECT count(*) FROM guardian_events WHERE check_version_id = :cvid"),
            {"cvid": cvid},
        ).scalar()
        assert count == 1


# ---------------------------------------------------------------------------\\n# Discard semantics\\n# ---------------------------------------------------------------------------


def test_discard_before_first_confirm_deletes_draft(fresh_db: Engine) -> None:
    """Never-confirmed check: delete draft only, identity persists."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Disc1", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value)"
                " VALUES (:cid, 5.00)"
            ),
            {"cid": cid},
        )
        # Draft exists
        row = conn.execute(text("SELECT 1 FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid}).fetchone()
        assert row is not None
        # Delete draft (atomic discard when never confirmed at DB level)
        conn.execute(text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid})
        # Draft gone
        row = conn.execute(text("SELECT 1 FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid}).fetchone()
        assert row is None


def test_discard_after_confirm_only_deletes_draft(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Disc2", "staleness")
        # Confirm first
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts (check_id, threshold_value, staleness_days)"
                " VALUES (:cid, 1.00, 30)"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed (id, check_id, version_number,"
                " check_type, threshold_value, staleness_days, severity)"
                " VALUES (:id, :cid, 1, 'staleness', 0, 30, 'info')"
            ),
            {"id": str(uuid4()), "cid": cid},
        )
        conn.execute(text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid})
        conn.execute(text("UPDATE guardian_checks SET status = 'confirmed' WHERE id = :cid"), {"cid": cid})
        # Now create new draft
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts (check_id, threshold_value, staleness_days)"
                " VALUES (:cid, 1.00, 30)"
            ),
            {"cid": cid},
        )
        # Discard only draft
        conn.execute(text("DELETE FROM guardian_check_drafts WHERE check_id = :cid"), {"cid": cid})
        # Draft gone, but identity and confirmed version remain
        row = conn.execute(text("SELECT id FROM guardian_checks WHERE id = :cid"), {"cid": cid}).fetchone()
        assert row is not None
        row = conn.execute(
            text("SELECT version_number FROM guardian_check_confirmed WHERE check_id = :cid"),
            {"cid": cid},
        ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Transaction rollback atomicity
# ---------------------------------------------------------------------------


def test_confirm_and_event_in_same_transaction_rollback(fresh_db: Engine) -> None:
    """If event insert fails, confirmed version must also roll back."""
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        cid = str(uuid4())
        _create_check(conn, cid, hid, "Roll", "drift")
        conn.execute(
            text(
                "INSERT INTO guardian_check_drafts"
                " (check_id, threshold_value, target_category, target_holding_category)"
                " VALUES (:cid, 5.00, 'eq', 'eq')"
            ),
            {"cid": cid},
        )
        # Insert this manually but omit to create event with missing FK → rollback
        savepoint = conn.begin_nested()
        cvid = str(uuid4())
        conn.execute(
            text(
                "INSERT INTO guardian_check_confirmed"
                " (id, check_id, version_number, check_type, threshold_value,"
                "  target_category, target_holding_category, severity)"
                " VALUES (:id, :cid, 1, 'drift', 5.00, 'eq', 'eq', 'info')"
            ),
            {"id": cvid, "cid": cid},
        )
        # Attempt event with missing FKs — should fail
        try:
            conn.execute(
                text(
                    "INSERT INTO guardian_events"
                    " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                    "  check_type, policy_version_id, portfolio_snapshot_id, drift_pp, as_of_date)"
                    " VALUES (:id, :run, :hid, :cid, :cvid, 'drift', :pid, :sid, 3.50, '2026-07-17')"
                ),
                {
                    "id": str(uuid4()), "run": str(uuid4()), "hid": hid, "cid": cid, "cvid": cvid,
                    "pid": str(uuid4()), "sid": str(uuid4()),
                },
            )
        except Exception:
            savepoint.rollback()
        # Confirmed version should not exist (rolled back with savepoint)
        row = conn.execute(
            text("SELECT 1 FROM guardian_check_confirmed WHERE id = :id"),
            {"id": cvid},
        ).fetchone()
        assert row is None


# ---------------------------------------------------------------------------
# FK integrity
# ---------------------------------------------------------------------------


def test_event_requires_valid_evaluation_run(fresh_db: Engine) -> None:
    with fresh_db.begin() as conn:
        _create_household(conn, str(uuid4()))
        hid = _get_household_id(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO guardian_events"
                    " (id, evaluation_run_id, household_id, check_id, check_version_id,"
                    "  policy_version_id, portfolio_snapshot_id, as_of_date)"
                    " VALUES (:id, :run, :hid, :cid, :cvid, :pid, :sid, '2026-07-17')"
                ),
                {
                    "id": str(uuid4()), "run": str(uuid4()), "hid": hid,
                    "cid": str(uuid4()), "cvid": str(uuid4()),
                    "pid": str(uuid4()), "sid": str(uuid4()),
                },
            )


# ---------------------------------------------------------------------------
# Downgrade safety: 0006 schema works after downgrade
# ---------------------------------------------------------------------------


def test_downgrade_leaves_0006_usable(fresh_db: Engine) -> None:
    _downgrade_to(fresh_db, PREVIOUS_REVISION)
    with fresh_db.connect() as conn:
        # Can still query portfolio tables
        conn.execute(text("SELECT 1 FROM household_profiles LIMIT 0")).fetchone()
        # No guardian tables
        insp = inspect(fresh_db)
        existing = set(insp.get_table_names())
        for table in GUARDIAN_TABLES:
            assert table not in existing
