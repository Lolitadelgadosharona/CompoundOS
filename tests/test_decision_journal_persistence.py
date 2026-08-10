from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import postgres_test_database_url

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0019_investment_policy_enrichment"
SLICE_3_REVISION = "0003_decision_journal_foundation"
SLICE_2_REVISION = "0002_investment_policy_foundation"
SLICE_1_REVISION = "0001_household_persistence"

PORTFOLIO_TABLES = {
    "portfolios",
    "accounts",
    "portfolio_drafts",
    "portfolio_draft_holdings",
    "portfolio_snapshots",
    "portfolio_snapshot_holdings",
}

DECISION_JOURNAL_TABLES = {
    "decisions",
    "decision_drafts",
    "decision_confirmed_snapshots",
    "decision_corrections",
}

SLICE_2_TABLES = {
    "investment_policies",
    "investment_policy_drafts",
    "investment_policy_draft_allocations",
    "investment_policy_versions",
    "investment_policy_version_allocations",
}

EXPECTED_DECISION_FUNCTIONS = {
    "fn_decision_identity_lifecycle",
    "fn_decision_identity_delete_guard",
    "fn_decision_confirmed_snapshot_immutability",
    "fn_decision_correction_immutability",
    "fn_decision_lifecycle_consistency",
}

EXPECTED_DECISION_TRIGGERS = {
    "trg_decision_identity_lifecycle",
    "trg_decision_identity_delete_guard",
    "trg_decision_confirmed_snapshot_immutability",
    "trg_decision_correction_immutability",
    "trg_decision_lifecycle_consistency",
    "trg_decision_lifecycle_consistency_draft",
    "trg_decision_lifecycle_consistency_snapshot",
}

SNAPSHOT_FIELDS = (
    "title, decision_summary, rationale, alternatives_considered,"
    " risks_and_uncertainties, evidence_or_sources, expected_outcome,"
    " review_trigger, review_date, decision_date, notes"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def create_household(connection) -> str:
    hid = uuid4()
    connection.execute(
        text(
            "INSERT INTO household_profiles "
            "(id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes) "
            "VALUES (:id, true, 'DJ Test', 'USD', '', '', '', '')"
        ),
        {"id": hid},
    )
    return str(hid)


def create_policy_version(connection, household_id: str) -> str:
    pid = uuid4()
    connection.execute(
        text(
            "INSERT INTO investment_policies (id, household_id) "
            "VALUES (:id, :hid)"
        ),
        {"id": pid, "hid": household_id},
    )
    vid = uuid4()
    connection.execute(
        text(
            "INSERT INTO investment_policy_versions "
            "(id, policy_id, version_number, status, published_at,"
            " objectives, time_horizon, liquidity, diversification,"
            " contribution_policy, rebalancing_policy, prohibited_assets,"
            " leverage_policy, decision_process, notes) "
            "VALUES (:id, :pid, 1, 'published', now(),"
            " 'obj', 'horizon', '', '', '', '', '', '', 'decide', '')"
        ),
        {"id": vid, "pid": pid},
    )
    connection.execute(
        text(
            "INSERT INTO investment_policy_version_allocations "
            "(id, version_id, asset_class_name, normalized_asset_class_name,"
            " target_percentage, sort_order) "
            "VALUES (:id, :vid, 'Cash', 'cash', 100.00, 0)"
        ),
        {"id": uuid4(), "vid": vid},
    )
    connection.execute(
        text(
            "UPDATE investment_policy_versions SET sealed_at = now() "
            "WHERE id = :id"
        ),
        {"id": vid},
    )
    return str(vid)


def create_decision_with_draft(connection, household_id: str) -> tuple[str, str]:
    did = uuid4()
    connection.execute(
        text(
            "INSERT INTO decisions (id, household_id, status) "
            "VALUES (:id, :hid, 'draft')"
        ),
        {"id": did, "hid": household_id},
    )
    drid = uuid4()
    connection.execute(
        text(
            "INSERT INTO decision_drafts "
            "(id, decision_id, title) VALUES (:id, :did, 'Test Draft')"
        ),
        {"id": drid, "did": did},
    )
    return str(did), str(drid)


def confirm_decision(
    connection,
    decision_id: str,
    draft_id: str,
    policy_version_id: str,
    *,
    decision_date: str = "CURRENT_DATE",
) -> str:
    sid = uuid4()
    date_expr = (
        f"'{decision_date}'::date"
        if decision_date != "CURRENT_DATE"
        else "CURRENT_DATE"
    )
    connection.execute(
        text(
            f"INSERT INTO decision_confirmed_snapshots "
            f"(id, decision_id, selected_policy_version_id, title,"
            f" decision_summary, rationale, decision_date, confirmed_at) "
            f"VALUES (:id, :did, :vid, 'Confirmed Title',"
            f" 'Summary text', 'Rationale text', {date_expr}, now())"
        ),
        {"id": sid, "did": decision_id, "vid": policy_version_id},
    )
    connection.execute(
        text("DELETE FROM decision_drafts WHERE id = :id"),
        {"id": draft_id},
    )
    connection.execute(
        text(
            "UPDATE decisions SET status = 'confirmed' WHERE id = :id"
        ),
        {"id": decision_id},
    )
    return str(sid)


def make_correction(
    connection,
    decision_id: str,
    snapshot_id: str,
    *,
    correction_number: int = 1,
    actor: str = "local-owner",
    reason: str = "Correction needed",
    decision_date: str = "CURRENT_DATE",
) -> None:
    cid = uuid4()
    date_expr = (
        f"'{decision_date}'::date"
        if decision_date != "CURRENT_DATE"
        else "CURRENT_DATE"
    )
    connection.execute(
        text(
            f"INSERT INTO decision_corrections "
            f"(id, decision_id, corrected_entry_id, correction_number,"
            f" correction_reason, actor, title, decision_summary,"
            f" rationale, decision_date) "
            f"VALUES (:id, :did, :sid, :cn, :reason, :actor,"
            f" 'Corrected Title', 'Corrected Summary',"
            f" 'Corrected Rationale', {date_expr})"
        ),
        {
            "id": cid,
            "did": decision_id,
            "sid": snapshot_id,
            "cn": correction_number,
            "reason": reason,
            "actor": actor,
        },
    )


def assert_db_error(connection, expected_identifier: str, operation) -> None:
    with pytest.raises(Exception) as exc_info:
        operation()
    assert expected_identifier in str(exc_info.value)
    connection.rollback()


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


@pytest.mark.postgres
def test_fresh_base_to_head_includes_all_slice_3_tables(
    db_session: Session,
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = postgres_test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    postgres_engine.dispose()
    migration_engine = create_engine(database_url, pool_pre_ping=True)

    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION

        inspector = inspect(migration_engine)
        table_names = set(inspector.get_table_names())
        assert PORTFOLIO_TABLES <= table_names
        assert DECISION_JOURNAL_TABLES <= table_names
        assert SLICE_2_TABLES <= table_names
        assert {"household_profiles", "audit_events"} <= table_names
    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


@pytest.mark.postgres
def test_incremental_upgrade_0002_to_0003_preserves_existing_data(
    db_session: Session,
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = postgres_test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    postgres_engine.dispose()
    migration_engine = create_engine(database_url, pool_pre_ping=True)
    household_id = uuid4()
    event_id = uuid4()

    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION

        command.downgrade(alembic_config, SLICE_1_REVISION)
        assert current_revision(migration_engine) == SLICE_1_REVISION

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO household_profiles "
                    "(id, singleton_key, household_name, base_currency,"
                    " investment_horizon, liquidity_needs, risk_statement, notes) "
                    "VALUES (:id, true, 'Migration Household', 'USD', '', '', '', '')"
                ),
                {"id": household_id},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                    "VALUES (:id, :household_id, 'local-owner', 'household.created', "
                    "'HouseholdProfile', :household_id, CAST('{}' AS jsonb))"
                ),
                {"id": event_id, "household_id": household_id},
            )

        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION

        with migration_engine.begin() as connection:
            assert connection.scalar(
                text("SELECT count(*) FROM household_profiles WHERE id = :id"),
                {"id": household_id},
            ) == 1
            assert connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE id = :id"),
                {"id": event_id},
            ) == 1

        inspector = inspect(migration_engine)
        table_names = set(inspector.get_table_names())
        assert DECISION_JOURNAL_TABLES <= table_names
        assert SLICE_2_TABLES <= table_names

    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


@pytest.mark.postgres
def test_downgrade_0003_to_0002_and_reupgrade(
    db_session: Session,
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = postgres_test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    postgres_engine.dispose()
    migration_engine = create_engine(database_url, pool_pre_ping=True)

    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

        command.downgrade(alembic_config, SLICE_2_REVISION)
        assert current_revision(migration_engine) == SLICE_2_REVISION

        inspector = inspect(migration_engine)
        table_names = set(inspector.get_table_names())
        assert not (DECISION_JOURNAL_TABLES & table_names)
        assert SLICE_2_TABLES <= table_names

        with migration_engine.connect() as connection:
            household_count = connection.scalar(
                text("SELECT count(*) FROM household_profiles")
            )
            assert household_count is not None

        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION

        inspector = inspect(migration_engine)
        assert DECISION_JOURNAL_TABLES <= set(inspector.get_table_names())
    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


def test_alembic_version_column_width_supports_head() -> None:
    assert len(HEAD_REVISION) <= 64


def test_application_never_calls_create_all() -> None:
    application_files = sorted(Path("apps").rglob("*.py"))
    offenders = [
        str(path)
        for path in application_files
        if ".create_all(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ---------------------------------------------------------------------------
# Schema inspection
# ---------------------------------------------------------------------------


def test_decision_journal_schema_constraints_fks_functions_triggers(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)
    table_names = set(inspector.get_table_names())
    assert DECISION_JOURNAL_TABLES <= table_names

    _ = {
        uc["name"] for uc in inspector.get_unique_constraints("decisions")
    }
    drafts_uniques = {
        uc["name"] for uc in inspector.get_unique_constraints("decision_drafts")
    }
    snapshots_uniques = {
        uc["name"]
        for uc in inspector.get_unique_constraints("decision_confirmed_snapshots")
    }
    corrections_uniques = {
        uc["name"]
        for uc in inspector.get_unique_constraints("decision_corrections")
    }
    assert "uq_decision_drafts_decision_id" in drafts_uniques
    assert "uq_decision_snapshots_decision_id" in snapshots_uniques
    assert (
        "uq_decision_corrections_decision_correction_number" in corrections_uniques
    )

    for table_name, expected_names in EXPECTED_DECISION_CHECKS.items():
        installed = {
            cc["name"] for cc in inspector.get_check_constraints(table_name)
        }
        assert expected_names <= installed, (
            f"Missing checks on {table_name}: {expected_names - installed}"
        )

    for table_name, expected_names in EXPECTED_DECISION_FKS.items():
        installed = {
            fk["name"] for fk in inspector.get_foreign_keys(table_name)
        }
        assert expected_names <= installed, (
            f"Missing FKs on {table_name}: {expected_names - installed}"
        )

    with postgres_engine.connect() as connection:
        functions = set(
            connection.scalars(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE proname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_DECISION_FUNCTIONS)},
            )
        )
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal "
                    "AND tgname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_DECISION_TRIGGERS)},
            )
        )
    assert functions == EXPECTED_DECISION_FUNCTIONS
    assert triggers == EXPECTED_DECISION_TRIGGERS


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------


def test_multiple_independent_decision_drafts_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did1, drid1 = create_decision_with_draft(conn, hid)
        did2, drid2 = create_decision_with_draft(conn, hid)
        conn.commit()

    assert did1 != did2
    assert drid1 != drid2


def test_at_most_one_draft_per_decision(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, _ = create_decision_with_draft(conn, hid)
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO decision_drafts "
                    "(id, decision_id, title) "
                    "VALUES (:id, :did, 'Second Draft')"
                ),
                {"id": uuid4(), "did": did},
            )
        conn.rollback()


def test_at_most_one_snapshot_per_decision(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO decision_confirmed_snapshots "
                    "(id, decision_id, selected_policy_version_id, title,"
                    " decision_summary, rationale, decision_date, confirmed_at) "
                    "VALUES (:id, :did, :vid, 'Dup', 'Dup', 'Dup', CURRENT_DATE, now())"
                ),
                {"id": uuid4(), "did": did, "vid": vid},
            )
        conn.rollback()


def test_draft_text_length_constraints(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, _ = create_decision_with_draft(conn, hid)
        conn.commit()

        with pytest.raises(Exception) as exc:
            conn.execute(
                text(
                    "UPDATE decision_drafts SET title = :long "
                    "WHERE decision_id = :did"
                ),
                {"long": "x" * 501, "did": did},
            )
        assert "ck_decision_drafts_title_length" in str(exc.value)
        conn.rollback()


def test_decision_date_yesterday_allowed(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))
        yesterday = (db_today - timedelta(days=1)).isoformat()
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(
            conn, did, drid, vid, decision_date=yesterday
        )
        conn.commit()


def test_decision_date_today_allowed(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()


def test_decision_date_tomorrow_rejected(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))

        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        tomorrow = (db_today + timedelta(days=1)).isoformat()
        with pytest.raises(Exception) as exc:
            confirm_decision(
                conn, did, drid, vid, decision_date=tomorrow
            )
            conn.commit()
        assert "decision_date_not_future" in str(exc.value)
        conn.rollback()


def test_snapshot_invalid_direct_date_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        with pytest.raises(Exception) as exc:
            conn.execute(
                text(
                    "INSERT INTO decision_confirmed_snapshots "
                    "(id, decision_id, selected_policy_version_id, title,"
                    " decision_summary, rationale, decision_date, confirmed_at) "
                    "VALUES (:id, :did, :vid, 'T', 'S', 'R',"
                    " '2099-12-31'::date, now())"
                ),
                {"id": uuid4(), "did": did, "vid": vid},
            )
        assert "decision_date_not_future" in str(exc.value)
        conn.rollback()


def test_decision_date_boundary_timezone_sensitive(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    """Verify that date checks respect the database timezone.

    Uses SET LOCAL TIME ZONE 'UTC' which auto-resets at transaction
    end — no pool contamination.
    """
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))
        yesterday = db_today - timedelta(days=1)
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(
            conn, did, drid, vid,
            decision_date=yesterday.isoformat(),
        )
        conn.commit()


def test_correction_uses_same_date_boundary(db_session: Session, postgres_engine: Engine) -> None:
    """Correction date must not be in the future — validated by DB clock.

    Reads CURRENT_DATE from PostgreSQL in a SET LOCAL UTC transaction
    so that tomorrow = DB_CURRENT_DATE + 1 day.  No Python date.today().
    SET LOCAL auto-resets at commit — no pool contamination.
    """
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))

        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()

        tomorrow = (db_today + timedelta(days=1)).isoformat()
        with pytest.raises(Exception) as exc:
            make_correction(
                conn,
                did,
                sid,
                correction_number=2,
                decision_date=tomorrow,
            )
            conn.commit()
        assert "decision_date_not_future" in str(exc.value)
        conn.rollback()


# ---------------------------------------------------------------------------
# Lifecycle consistency
# ---------------------------------------------------------------------------


def test_valid_draft_creation_transaction(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, _drid = create_decision_with_draft(conn, hid)
        conn.commit()

        count = conn.scalar(
            text("SELECT count(*) FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert count == 1

        status = conn.scalar(
            text("SELECT status FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert status == "draft"


def test_draft_status_without_draft_row_cannot_commit(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did = uuid4()
        conn.execute(
            text(
                "INSERT INTO decisions (id, household_id, status) "
                "VALUES (:id, :hid, 'draft')"
            ),
            {"id": did, "hid": hid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_draft_requires_draft_row" in str(exc.value)
        conn.rollback()


def test_confirmed_status_without_snapshot_cannot_commit(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, drid = create_decision_with_draft(conn, hid)
        conn.execute(
            text("DELETE FROM decision_drafts WHERE id = :id"),
            {"id": drid},
        )
        conn.execute(
            text(
                "UPDATE decisions SET status = 'confirmed' WHERE id = :id"
            ),
            {"id": did},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        error_msg = str(exc.value)
        assert (
            "decision_confirmed_requires_snapshot" in error_msg
            or "decision_draft_requires_draft_row" in error_msg
        )
        conn.rollback()


def test_draft_and_snapshot_coexist_cannot_commit(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        conn.execute(
            text(
                "INSERT INTO decision_confirmed_snapshots "
                "(id, decision_id, selected_policy_version_id, title,"
                " decision_summary, rationale, decision_date, confirmed_at) "
                "VALUES (:id, :did, :vid, 'T', 'S', 'R', CURRENT_DATE, now())"
            ),
            {"id": uuid4(), "did": did, "vid": vid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_draft_has_snapshot" in str(exc.value)
        conn.rollback()


# ---------------------------------------------------------------------------
# Deferred trigger bypass regression tests (cross-transaction)
# ---------------------------------------------------------------------------


def test_existing_draft_update_to_confirmed_without_snapshot_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    """Bypass scenario 1: UPDATE existing draft to confirmed without snapshot."""
    # Transaction 1: Create draft decision
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, _drid = create_decision_with_draft(conn, hid)
        conn.commit()

    # Transaction 2: Update to confirmed without snapshot (should fail)
    with postgres_engine.connect() as conn:
        conn.execute(
            text("UPDATE decisions SET status = 'confirmed' WHERE id = :id"),
            {"id": did},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_confirmed_requires_snapshot" in str(exc.value)
        conn.rollback()


def test_existing_draft_delete_draft_row_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    """Bypass scenario 2: DELETE draft from existing draft decision."""
    # Transaction 1: Create draft decision
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, drid = create_decision_with_draft(conn, hid)
        conn.commit()

    # Transaction 2: Delete draft without deleting decision (should fail)
    with postgres_engine.connect() as conn:
        conn.execute(
            text("DELETE FROM decision_drafts WHERE id = :id"),
            {"id": drid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_draft_requires_draft_row" in str(exc.value)
        conn.rollback()


def test_existing_draft_insert_snapshot_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    """Bypass scenario 3: INSERT snapshot for existing draft decision."""
    # Transaction 1: Create draft decision
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, _drid = create_decision_with_draft(conn, hid)
        conn.commit()

    # Transaction 2: Insert snapshot without confirming (should fail)
    with postgres_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO decision_confirmed_snapshots "
                "(id, decision_id, selected_policy_version_id, title,"
                " decision_summary, rationale, decision_date, confirmed_at) "
                "VALUES (:id, :did, :vid, 'T', 'S', 'R', CURRENT_DATE, now())"
            ),
            {"id": uuid4(), "did": did, "vid": vid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_draft_has_snapshot" in str(exc.value)
        conn.rollback()


def test_existing_confirmed_insert_draft_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    """Bypass scenario 4: INSERT draft for existing confirmed decision."""
    # Transaction 1: Create confirmed decision
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

    # Transaction 2: Insert draft for confirmed decision (should fail)
    with postgres_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO decision_drafts "
                "(id, decision_id, title) VALUES (:id, :did, 'Late Draft')"
            ),
            {"id": uuid4(), "did": did},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "decision_confirmed_has_draft" in str(exc.value)
        conn.rollback()


def test_draft_to_confirmed_success(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        status = conn.scalar(
            text("SELECT status FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert status == "confirmed"


def test_confirmed_to_archived_success(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now(),"
                " archive_reason = 'No longer relevant' "
                "WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT status, archived_at, archive_reason "
                "FROM decisions WHERE id = :id"
            ),
            {"id": did},
        ).one()
        assert row.status == "archived"
        assert row.archived_at is not None
        assert row.archive_reason == "No longer relevant"


def test_archived_to_confirmed_success(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now(), archive_reason = 'Archive' "
                "WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'confirmed',"
                " archived_at = NULL, archive_reason = NULL "
                "WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT status, archived_at, archive_reason "
                "FROM decisions WHERE id = :id"
            ),
            {"id": did},
        ).one()
        assert row.status == "confirmed"
        assert row.archived_at is None
        assert row.archive_reason is None


def test_forbidden_transitions_fail(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now() WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        assert_db_error(
            conn,
            "decision_identity_invalid_status_transition",
            lambda: conn.execute(
                text(
                    "UPDATE decisions SET status = 'draft',"
                    " archived_at = NULL WHERE id = :id"
                ),
                {"id": did},
            ),
        )


def test_archive_requires_archived_at(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_archive_requires_archived_at",
            lambda: conn.execute(
                text(
                    "UPDATE decisions SET status = 'archived',"
                    " archive_reason = 'test' "
                    "WHERE id = :id"
                ),
                {"id": did},
            ),
        )


def test_unarchive_clears_archive_fields(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now(),"
                " archive_reason = 'Test archive' "
                "WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'confirmed',"
                " archived_at = NULL, archive_reason = NULL "
                "WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT status, archived_at, archive_reason "
                "FROM decisions WHERE id = :id"
            ),
            {"id": did},
        ).one()
        assert row.status == "confirmed"
        assert row.archived_at is None
        assert row.archive_reason is None


def test_archive_fields_only_during_transition(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_archive_fields_only_during_transition",
            lambda: conn.execute(
                text(
                    "UPDATE decisions SET archive_reason = 'No transition' "
                    "WHERE id = :id"
                ),
                {"id": did},
            ),
        )


# ---------------------------------------------------------------------------
# Discard foundation
# ---------------------------------------------------------------------------


def test_atomic_draft_and_identity_delete(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, drid = create_decision_with_draft(conn, hid)
        conn.commit()

        conn.execute(
            text("DELETE FROM decision_drafts WHERE id = :id"),
            {"id": drid},
        )
        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"),
            {"id": did},
        )
        conn.commit()

        count = conn.scalar(
            text("SELECT count(*) FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert count == 0


def test_audit_event_stable_on_identity_delete(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, drid = create_decision_with_draft(conn, hid)
        event_id = uuid4()
        conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type,"
                " entity_id, metadata) "
                "VALUES (:id, :hid, 'local-owner', 'decision.created',"
                " 'Decision', :did, CAST('{}' AS jsonb))"
            ),
            {"id": event_id, "hid": hid, "did": did},
        )
        conn.commit()

        conn.execute(
            text("DELETE FROM decision_drafts WHERE id = :id"),
            {"id": drid},
        )
        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"),
            {"id": did},
        )
        conn.commit()

        event_count = conn.scalar(
            text("SELECT count(*) FROM audit_events WHERE id = :id"),
            {"id": event_id},
        )
        assert event_count == 1


def test_confirmed_identity_delete_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_identity_delete_forbidden",
            lambda: conn.execute(
                text("DELETE FROM decisions WHERE id = :id"),
                {"id": did},
            ),
        )


def test_archived_identity_delete_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now() WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        assert_db_error(
            conn,
            "decision_identity_delete_forbidden",
            lambda: conn.execute(
                text("DELETE FROM decisions WHERE id = :id"),
                {"id": did},
            ),
        )


def test_identity_delete_failure_rollback(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_identity_delete_forbidden",
            lambda: conn.execute(
                text("DELETE FROM decisions WHERE id = :id"),
                {"id": did},
            ),
        )

        count = conn.scalar(
            text("SELECT count(*) FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert count == 1
        status = conn.scalar(
            text("SELECT status FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert status == "confirmed"


def test_multi_row_delete_guard(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did1, drid1 = create_decision_with_draft(conn, hid)
        did2, drid2 = create_decision_with_draft(conn, hid)
        vid = create_policy_version(conn, hid)
        confirm_decision(conn, did2, drid2, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_identity_delete_forbidden",
            lambda: conn.execute(text("DELETE FROM decisions")),
        )


def test_draft_cascade_on_identity_delete(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        did, drid = create_decision_with_draft(conn, hid)
        conn.commit()

        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"),
            {"id": did},
        )
        conn.commit()

        draft_count = conn.scalar(
            text(
                "SELECT count(*) FROM decision_drafts "
                "WHERE decision_id = :did"
            ),
            {"did": did},
        )
        assert draft_count == 0


# ---------------------------------------------------------------------------
# Snapshot immutability
# ---------------------------------------------------------------------------


def test_snapshot_insert_valid(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        title = conn.scalar(
            text(
                "SELECT title FROM decision_confirmed_snapshots "
                "WHERE id = :id"
            ),
            {"id": sid},
        )
        assert title == "Confirmed Title"


def test_snapshot_update_any_field_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_snapshot_update_forbidden",
            lambda: conn.execute(
                text(
                    "UPDATE decision_confirmed_snapshots "
                    "SET title = 'Changed' WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_snapshot_policy_version_update_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        # The immutability trigger blocks ALL updates to snapshots,
        # so updating to the same policy_version_id is sufficient to test.
        assert_db_error(
            conn,
            "decision_snapshot_update_forbidden",
            lambda: conn.execute(
                text(
                    "UPDATE decision_confirmed_snapshots "
                    "SET selected_policy_version_id = :vid "
                    "WHERE id = :id"
                ),
                {"id": sid, "vid": vid},
            ),
        )


def test_snapshot_delete_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_snapshot_delete_forbidden",
            lambda: conn.execute(
                text(
                    "DELETE FROM decision_confirmed_snapshots "
                    "WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_snapshot_multi_row_update_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did1, drid1 = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did1, drid1, vid)
        did2, drid2 = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did2, drid2, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_snapshot_update_forbidden",
            lambda: conn.execute(
                text(
                    "UPDATE decision_confirmed_snapshots "
                    "SET created_at = now()"
                )
            ),
        )


def test_snapshot_fk_restrict(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "policy_version_delete_forbidden",
            lambda: conn.execute(
                text(
                    "DELETE FROM investment_policy_versions "
                    "WHERE id = :vid"
                ),
                {"vid": vid},
            ),
        )


def test_snapshot_rollback_session_reuse(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_snapshot_update_forbidden",
            lambda: conn.execute(
                text(
                    "UPDATE decision_confirmed_snapshots "
                    "SET title = 'X' WHERE id = :id"
                ),
                {"id": sid},
            ),
        )

        title = conn.scalar(
            text(
                "SELECT title FROM decision_confirmed_snapshots "
                "WHERE id = :id"
            ),
            {"id": sid},
        )
        assert title == "Confirmed Title"


# ---------------------------------------------------------------------------
# Correction
# ---------------------------------------------------------------------------


def test_correction_insert_valid(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM decision_corrections "
                "WHERE decision_id = :did"
            ),
            {"did": did},
        )
        assert count == 1


def test_correction_confirmed_decision_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        status = conn.scalar(
            text("SELECT status FROM decisions WHERE id = :id"),
            {"id": did},
        )
        assert status == "confirmed"

        make_correction(conn, did, sid)
        conn.commit()


def test_correction_archived_decision_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        conn.execute(
            text(
                "UPDATE decisions SET status = 'archived',"
                " archived_at = now() WHERE id = :id"
            ),
            {"id": did},
        )
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()


def test_correction_draft_decision_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        conn.commit()

        fake_sid = uuid4()
        conn.execute(
            text(
                "INSERT INTO decision_confirmed_snapshots "
                "(id, decision_id, selected_policy_version_id, title,"
                " decision_summary, rationale, decision_date, confirmed_at) "
                "VALUES (:id, :did, :vid, 'T', 'S', 'R', CURRENT_DATE, now())"
            ),
            {"id": fake_sid, "did": did, "vid": vid},
        )

        assert_db_error(
            conn,
            "decision_correction_draft_not_allowed",
            lambda: make_correction(conn, did, str(fake_sid)),
        )


def test_correction_update_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_correction_update_forbidden",
            lambda: conn.execute(
                text(
                    "UPDATE decision_corrections "
                    "SET correction_reason = 'Changed' "
                    "WHERE decision_id = :did"
                ),
                {"did": did},
            ),
        )


def test_correction_delete_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_correction_delete_forbidden",
            lambda: conn.execute(
                text(
                    "DELETE FROM decision_corrections "
                    "WHERE decision_id = :did"
                ),
                {"did": did},
            ),
        )


def test_correction_wrong_actor_fails(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_correction_invalid_actor",
            lambda: make_correction(
                conn, did, sid, actor="admin"
            ),
        )


def test_correction_ownership_mismatch_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did_a, drid_a = create_decision_with_draft(conn, hid)
        confirm_decision(conn, did_a, drid_a, vid)
        did_b, drid_b = create_decision_with_draft(conn, hid)
        sid_b = confirm_decision(conn, did_b, drid_b, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_correction_ownership_mismatch",
            lambda: make_correction(conn, did_a, sid_b),
        )


def test_correction_selected_policy_version_not_in_table(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)
    column_names = {
        col["name"]
        for col in inspector.get_columns("decision_corrections")
    }
    assert "selected_policy_version_id" not in column_names


def test_duplicate_correction_number_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid, correction_number=1)
        conn.commit()

        assert_db_error(
            conn,
            "uq_decision_corrections_decision_correction_number",
            lambda: make_correction(
                conn,
                did,
                sid,
                correction_number=1,
                reason="Duplicate",
            ),
        )


def test_different_decisions_same_correction_number(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did_a, drid_a = create_decision_with_draft(conn, hid)
        sid_a = confirm_decision(conn, did_a, drid_a, vid)
        did_b, drid_b = create_decision_with_draft(conn, hid)
        sid_b = confirm_decision(conn, did_b, drid_b, vid)
        conn.commit()

        make_correction(conn, did_a, sid_a, correction_number=1)
        make_correction(conn, did_b, sid_b, correction_number=1)
        conn.commit()


def test_same_decision_sequential_correction_numbers(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid, correction_number=1)
        make_correction(
            conn,
            did,
            sid,
            correction_number=2,
            reason="Second correction",
        )
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM decision_corrections "
                "WHERE decision_id = :did"
            ),
            {"did": did},
        )
        assert count == 2


def test_correction_fk_restrict(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        make_correction(conn, did, sid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_snapshot_delete_forbidden",
            lambda: conn.execute(
                text(
                    "DELETE FROM decision_confirmed_snapshots "
                    "WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_correction_rollback_session_reuse(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        vid = create_policy_version(conn, hid)
        did, drid = create_decision_with_draft(conn, hid)
        sid = confirm_decision(conn, did, drid, vid)
        conn.commit()

        assert_db_error(
            conn,
            "decision_correction_invalid_actor",
            lambda: make_correction(
                conn, did, sid, actor="bad-actor"
            ),
        )

        count = conn.scalar(
            text(
                "SELECT count(*) FROM decision_corrections "
                "WHERE decision_id = :did"
            ),
            {"did": did},
        )
        assert count == 0

        make_correction(conn, did, sid)
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM decision_corrections "
                "WHERE decision_id = :did"
            ),
            {"did": did},
        )
        assert count == 1


# ---------------------------------------------------------------------------
# Trigger inspection
# ---------------------------------------------------------------------------


def test_exact_function_names_exist(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        functions = set(
            connection.scalars(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE proname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_DECISION_FUNCTIONS)},
            )
        )
    assert functions == EXPECTED_DECISION_FUNCTIONS


def test_exact_trigger_names_exist(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal "
                    "AND tgname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_DECISION_TRIGGERS)},
            )
        )
    assert triggers == EXPECTED_DECISION_TRIGGERS


def test_lifecycle_consistency_trigger_is_deferred(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        # Verify decisions trigger
        row = connection.execute(
            text(
                "SELECT tgdeferrable, tginitdeferred "
                "FROM pg_trigger "
                "WHERE tgname = 'trg_decision_lifecycle_consistency'"
            )
        ).one()
        assert row.tgdeferrable is True
        assert row.tginitdeferred is True

        # Verify decision_drafts trigger
        row = connection.execute(
            text(
                "SELECT tgdeferrable, tginitdeferred "
                "FROM pg_trigger "
                "WHERE tgname = 'trg_decision_lifecycle_consistency_draft'"
            )
        ).one()
        assert row.tgdeferrable is True
        assert row.tginitdeferred is True

        # Verify decision_confirmed_snapshots trigger
        row = connection.execute(
            text(
                "SELECT tgdeferrable, tginitdeferred "
                "FROM pg_trigger "
                "WHERE tgname = 'trg_decision_lifecycle_consistency_snapshot'"
            )
        ).one()
        assert row.tgdeferrable is True
        assert row.tginitdeferred is True


def test_trigger_error_identifiers(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        lifecycle_src = connection.scalar(
            text(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = 'fn_decision_identity_lifecycle'"
            )
        )
        for ident in (
            "decision_identity_created_at_immutable",
            "decision_identity_invalid_status_transition",
            "decision_archive_requires_archived_at",
            "decision_unarchive_must_clear_archive_fields",
            "decision_archive_fields_only_during_transition",
            "decision_identity_id_immutable",
            "decision_identity_household_immutable",
        ):
            assert ident in lifecycle_src, f"Missing: {ident}"

        guard_src = connection.scalar(
            text(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = 'fn_decision_identity_delete_guard'"
            )
        )
        for ident in (
            "decision_identity_delete_forbidden",
            "decision_identity_delete_has_snapshot",
        ):
            assert ident in guard_src, f"Missing: {ident}"

        snap_src = connection.scalar(
            text(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = "
                "'fn_decision_confirmed_snapshot_immutability'"
            )
        )
        for ident in (
            "decision_snapshot_delete_forbidden",
            "decision_snapshot_update_forbidden",
            "decision_snapshot_insert_invalid",
        ):
            assert ident in snap_src, f"Missing: {ident}"

        corr_src = connection.scalar(
            text(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = "
                "'fn_decision_correction_immutability'"
            )
        )
        for ident in (
            "decision_correction_update_forbidden",
            "decision_correction_delete_forbidden",
            "decision_correction_invalid_actor",
            "decision_correction_invalid_number",
            "decision_correction_snapshot_not_found",
            "decision_correction_ownership_mismatch",
            "decision_correction_draft_not_allowed",
        ):
            assert ident in corr_src, f"Missing: {ident}"

        cons_src = connection.scalar(
            text(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = 'fn_decision_lifecycle_consistency'"
            )
        )
        for ident in (
            "decision_confirmed_requires_snapshot",
            "decision_confirmed_has_draft",
            "decision_draft_has_snapshot",
            "decision_draft_requires_draft_row",
        ):
            assert ident in cons_src, f"Missing: {ident}"


def test_slice_2a_policy_triggers_still_exist(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    expected_policy_triggers = {
        "trg_investment_policy_version_immutability",
        "trg_investment_policy_version_allocation_immutability",
        "trg_investment_policy_version_sealed_at_commit",
    }
    with postgres_engine.connect() as connection:
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal "
                    "AND tgname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(expected_policy_triggers)},
            )
        )
    assert triggers == expected_policy_triggers


EXPECTED_DECISION_CHECKS = {
    "decisions": {
        "ck_decisions_status_values",
        "ck_decisions_archive_reason_length",
    },
    "decision_drafts": {
        "ck_decision_drafts_title_length",
        "ck_decision_drafts_decision_summary_length",
        "ck_decision_drafts_rationale_length",
        "ck_decision_drafts_alternatives_considered_length",
        "ck_decision_drafts_risks_and_uncertainties_length",
        "ck_decision_drafts_evidence_or_sources_length",
        "ck_decision_drafts_expected_outcome_length",
        "ck_decision_drafts_review_trigger_length",
        "ck_decision_drafts_notes_length",
        "ck_decision_drafts_revision_positive",
    },
    "decision_confirmed_snapshots": {
        "ck_decision_snapshots_title_length",
        "ck_decision_snapshots_decision_summary_length",
        "ck_decision_snapshots_rationale_length",
        "ck_decision_snapshots_alternatives_considered_length",
        "ck_decision_snapshots_risks_and_uncertainties_length",
        "ck_decision_snapshots_evidence_or_sources_length",
        "ck_decision_snapshots_expected_outcome_length",
        "ck_decision_snapshots_review_trigger_length",
        "ck_decision_snapshots_notes_length",
        "ck_decision_snapshots_decision_date_not_future",
    },
    "decision_corrections": {
        "ck_decision_corrections_title_length",
        "ck_decision_corrections_decision_summary_length",
        "ck_decision_corrections_rationale_length",
        "ck_decision_corrections_alternatives_considered_length",
        "ck_decision_corrections_risks_and_uncertainties_length",
        "ck_decision_corrections_evidence_or_sources_length",
        "ck_decision_corrections_expected_outcome_length",
        "ck_decision_corrections_review_trigger_length",
        "ck_decision_corrections_notes_length",
        "ck_decision_corrections_correction_reason_length",
        "ck_decision_corrections_decision_date_not_future",
        "ck_decision_corrections_correction_number_positive",
        "ck_decision_corrections_actor_local_owner",
    },
}

EXPECTED_DECISION_FKS = {
    "decisions": {
        "fk_decisions_household_id_household_profiles",
    },
    "decision_drafts": {
        "fk_decision_drafts_decision_id_decisions",
    },
    "decision_confirmed_snapshots": {
        "fk_decision_snapshots_decision_id_decisions",
        "fk_decision_snapshots_policy_version_id_policy_versions",
    },
    "decision_corrections": {
        "fk_decision_corrections_decision_id_decisions",
        "fk_decision_corrections_corrected_entry_id_snapshots",
    },
}
