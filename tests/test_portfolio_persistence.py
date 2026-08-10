from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
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

HEAD_REVISION = "0022_committee_bridge"
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

SLICE_3_TABLES = {
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

EXPECTED_PORTFOLIO_FUNCTIONS = {
    "fn_portfolio_snapshot_immutability",
    "fn_portfolio_snapshot_holdings_immutability",
    "fn_portfolio_lifecycle",
    "fn_portfolio_current_snapshot",
    "fn_portfolio_draft_holdings_consistency",
}

EXPECTED_PORTFOLIO_TRIGGERS = {
    "trg_portfolio_snapshot_immutability",
    "trg_portfolio_snapshot_holdings_immutability",
    "trg_portfolio_lifecycle",
    "trg_portfolio_current_snapshot",
    "trg_portfolio_draft_holdings_consistency_portfolios",
    "trg_portfolio_draft_holdings_consistency_drafts",
}


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
            "VALUES (:id, true, 'Portfolio Test', 'USD', '', '', '', '')"
        ),
        {"id": hid},
    )
    return str(hid)


def create_portfolio(connection, household_id: str, *, status: str = "draft") -> str:
    pid = uuid4()
    connection.execute(
        text(
            "INSERT INTO portfolios (id, household_id, status) "
            "VALUES (:id, :hid, :status)"
        ),
        {"id": pid, "hid": household_id, "status": status},
    )
    return str(pid)


def create_portfolio_with_draft(
    connection, household_id: str
) -> str:
    pid = create_portfolio(connection, household_id)
    connection.execute(
        text(
            "INSERT INTO portfolio_drafts (portfolio_id) VALUES (:pid)"
        ),
        {"pid": pid},
    )
    return pid


def create_draft_holding(
    connection,
    portfolio_id: str,
    *,
    asset_name: str = "Test Asset",
    asset_category: str = "equity",
    quantity: Decimal = Decimal("100"),
    unit_price: Decimal = Decimal("50"),
    total_value: Decimal = Decimal("5000.00"),
    valuation_date: str | None = None,
    notes: str | None = None,
    account_id: str | None = None,
    sort_order: int = 0,
) -> str:
    hid = uuid4()
    val_date = valuation_date or date.today().isoformat()
    connection.execute(
        text(
            "INSERT INTO portfolio_draft_holdings "
            "(id, portfolio_id, asset_name, asset_category, quantity,"
            " unit_price, total_value, valuation_date, notes, account_id, sort_order) "
            "VALUES (:id, :pid, :name, :cat, :qty, :price, :total,"
            " CAST(:val_date AS date), :notes, :acct, :sort)"
        ),
        {
            "id": hid,
            "pid": portfolio_id,
            "name": asset_name,
            "cat": asset_category,
            "qty": str(quantity),
            "price": str(unit_price),
            "total": str(total_value),
            "val_date": val_date,
            "notes": notes,
            "acct": account_id,
            "sort": sort_order,
        },
    )
    return str(hid)


def confirm_portfolio(
    connection,
    portfolio_id: str,
    *,
    version_number: int = 1,
    valuation_date: str | None = None,
    notes: str | None = None,
    holding_count: int | None = None,
) -> str:
    sid = uuid4()
    val_date = valuation_date or date.today().isoformat()
    connection.execute(
        text(
            "INSERT INTO portfolio_snapshots "
            "(id, portfolio_id, version_number, status, valuation_date,"
            " confirmed_at, holding_count, notes) "
            "VALUES (:id, :pid, :vn, 'current', CAST(:val_date AS date),"
            " now(), :hc, :notes)"
        ),
        {
            "id": sid,
            "pid": portfolio_id,
            "vn": version_number,
            "val_date": val_date,
            "hc": holding_count,
            "notes": notes,
        },
    )
    # Delete draft holdings and draft
    connection.execute(
        text("DELETE FROM portfolio_draft_holdings WHERE portfolio_id = :pid"),
        {"pid": portfolio_id},
    )
    connection.execute(
        text("DELETE FROM portfolio_drafts WHERE portfolio_id = :pid"),
        {"pid": portfolio_id},
    )
    connection.execute(
        text("UPDATE portfolios SET status = 'active' WHERE id = :pid"),
        {"pid": portfolio_id},
    )
    return str(sid)


def insert_snapshot_holding(
    connection,
    snapshot_id: str,
    *,
    asset_name: str = "Snapshot Asset",
    asset_category: str = "equity",
    quantity: Decimal = Decimal("100"),
    unit_price: Decimal = Decimal("50"),
    total_value: Decimal = Decimal("5000.00"),
    valuation_date: str | None = None,
    notes: str | None = None,
    account_id: str | None = None,
    sort_order: int = 0,
) -> str:
    hid = uuid4()
    val_date = valuation_date or date.today().isoformat()
    connection.execute(
        text(
            "INSERT INTO portfolio_snapshot_holdings "
            "(id, snapshot_id, asset_name, asset_category, quantity,"
            " unit_price, total_value, valuation_date, notes, account_id, sort_order) "
            "VALUES (:id, :sid, :name, :cat, :qty, :price, :total,"
            " CAST(:val_date AS date), :notes, :acct, :sort)"
        ),
        {
            "id": hid,
            "sid": snapshot_id,
            "name": asset_name,
            "cat": asset_category,
            "qty": str(quantity),
            "price": str(unit_price),
            "total": str(total_value),
            "val_date": val_date,
            "notes": notes,
            "acct": account_id,
            "sort": sort_order,
        },
    )
    return str(hid)


def assert_db_error(connection, expected_identifier: str, operation) -> None:
    with pytest.raises(Exception) as exc_info:
        operation()
    assert expected_identifier in str(exc_info.value)
    connection.rollback()


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


@pytest.mark.postgres
def test_fresh_base_to_head_includes_all_portfolio_tables(
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
        assert SLICE_3_TABLES <= table_names
        assert SLICE_2_TABLES <= table_names
        assert {"household_profiles", "audit_events"} <= table_names
    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


@pytest.mark.postgres
def test_incremental_upgrade_0003_to_0004_preserves_existing_data(
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

        command.downgrade(alembic_config, SLICE_3_REVISION)
        assert current_revision(migration_engine) == SLICE_3_REVISION

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
        assert PORTFOLIO_TABLES <= table_names
        assert SLICE_3_TABLES <= table_names

    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


@pytest.mark.postgres
def test_downgrade_0004_to_0003_and_reupgrade(
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

        command.downgrade(alembic_config, SLICE_3_REVISION)
        assert current_revision(migration_engine) == SLICE_3_REVISION

        inspector = inspect(migration_engine)
        table_names = set(inspector.get_table_names())
        assert not (PORTFOLIO_TABLES & table_names)
        assert SLICE_3_TABLES <= table_names

        with migration_engine.connect() as connection:
            household_count = connection.scalar(
                text("SELECT count(*) FROM household_profiles")
            )
            assert household_count is not None

        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION

        inspector = inspect(migration_engine)
        assert PORTFOLIO_TABLES <= set(inspector.get_table_names())
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


def test_portfolio_schema_constraints_fks_functions_triggers(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)
    table_names = set(inspector.get_table_names())
    assert PORTFOLIO_TABLES <= table_names

    # Unique constraints
    portfolios_uniques = {
        uc["name"] for uc in inspector.get_unique_constraints("portfolios")
    }
    assert "uq_portfolios_household_id" in portfolios_uniques

    snapshots_uniques = {
        uc["name"] for uc in inspector.get_unique_constraints("portfolio_snapshots")
    }
    assert "uq_portfolio_snapshots_portfolio_version" in snapshots_uniques

    # Named check constraints
    for table_name, expected_names in EXPECTED_PORTFOLIO_CHECKS.items():
        installed = {
            cc["name"] for cc in inspector.get_check_constraints(table_name)
        }
        assert expected_names <= installed, (
            f"Missing checks on {table_name}: {expected_names - installed}"
        )

    # Foreign keys
    for table_name, expected_names in EXPECTED_PORTFOLIO_FKS.items():
        installed = {
            fk["name"] for fk in inspector.get_foreign_keys(table_name)
        }
        assert expected_names <= installed, (
            f"Missing FKs on {table_name}: {expected_names - installed}"
        )

    # Trigger functions and triggers
    with postgres_engine.connect() as connection:
        functions = set(
            connection.scalars(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE proname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_PORTFOLIO_FUNCTIONS)},
            )
        )
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal "
                    "AND tgname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_PORTFOLIO_TRIGGERS)},
            )
        )
    assert functions == EXPECTED_PORTFOLIO_FUNCTIONS
    assert triggers == EXPECTED_PORTFOLIO_TRIGGERS


# ---------------------------------------------------------------------------
# Cardinality
# ---------------------------------------------------------------------------


def test_one_portfolio_per_household(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        create_portfolio_with_draft(conn, hid)
        conn.commit()

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO portfolios (id, household_id, status) "
                    "VALUES (:id, :hid, 'draft')"
                ),
                {"id": uuid4(), "hid": hid},
            )
            conn.execute(
                text(
                    "INSERT INTO portfolio_drafts (portfolio_id) VALUES (:id)"
                ),
                {"id": uuid4()},
            )
            conn.commit()
        conn.rollback()


def test_at_most_one_draft_per_portfolio(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO portfolio_drafts (portfolio_id) "
                    "VALUES (:pid)"
                ),
                {"pid": pid},
            )
        conn.rollback()


# ---------------------------------------------------------------------------
# Portfolio status transitions
# ---------------------------------------------------------------------------


def test_portfolio_draft_to_active_transition_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        confirm_portfolio(conn, pid)
        conn.commit()

        status = conn.scalar(
            text("SELECT status FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        assert status == "active"


def test_portfolio_active_to_draft_transition_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        confirm_portfolio(conn, pid)
        conn.commit()

        # Create new draft (active → draft)
        conn.execute(
            text("UPDATE portfolios SET status = 'draft' WHERE id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("INSERT INTO portfolio_drafts (portfolio_id) VALUES (:pid)"),
            {"pid": pid},
        )
        conn.commit()

        status = conn.scalar(
            text("SELECT status FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        assert status == "draft"


def test_portfolio_invalid_status_transition_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        assert_db_error(
            conn,
            "portfolio_invalid_status_transition",
            lambda: conn.execute(
                text("UPDATE portfolios SET status = 'nonexistent' WHERE id = :pid"),
                {"pid": pid},
            ),
        )


def test_portfolio_identity_fields_immutable(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        assert_db_error(
            conn,
            "portfolio_id_immutable",
            lambda: conn.execute(
                text("UPDATE portfolios SET id = :newid WHERE id = :pid"),
                {"newid": uuid4(), "pid": pid},
            ),
        )

        assert_db_error(
            conn,
            "portfolio_household_immutable",
            lambda: conn.execute(
                text(
                    "UPDATE portfolios SET household_id = :newhid WHERE id = :pid"
                ),
                {"newhid": uuid4(), "pid": pid},
            ),
        )


# ---------------------------------------------------------------------------
# Draft singleton and CRUD
# ---------------------------------------------------------------------------


def test_draft_singleton_per_portfolio(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_drafts "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert count == 1


def test_draft_holdings_crud(db_session: Session, postgres_engine: Engine) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        # Create holding
        holding_id = create_draft_holding(conn, pid)
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_draft_holdings "
                "WHERE id = :hid"
            ),
            {"hid": holding_id},
        )
        assert count == 1

        # Update holding
        conn.execute(
            text(
                "UPDATE portfolio_draft_holdings SET quantity = '200' "
                "WHERE id = :hid"
            ),
            {"hid": holding_id},
        )
        conn.commit()
        qty = conn.scalar(
            text(
                "SELECT quantity FROM portfolio_draft_holdings "
                "WHERE id = :hid"
            ),
            {"hid": holding_id},
        )
        assert str(qty) == "200.00000000"

        # Delete holding
        conn.execute(
            text("DELETE FROM portfolio_draft_holdings WHERE id = :hid"),
            {"hid": holding_id},
        )
        conn.commit()
        count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_draft_holdings "
                "WHERE id = :hid"
            ),
            {"hid": holding_id},
        )
        assert count == 0


def test_draft_cascade_deletes_holdings(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        # Delete the portfolio entirely (draft cascades on CASCADE FK)
        # First delete draft holdings, draft, then portfolio
        conn.execute(
            text("DELETE FROM portfolio_draft_holdings WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolio_drafts WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        conn.commit()

        holding_count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_draft_holdings "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        draft_count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_drafts "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        port_count = conn.scalar(
            text("SELECT count(*) FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        assert holding_count == 0
        assert draft_count == 0
        assert port_count == 0


# ---------------------------------------------------------------------------
# Decimal precision boundaries
# ---------------------------------------------------------------------------


def test_decimal_precision_quantity_max_boundary(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(
            conn,
            pid,
            quantity=Decimal("999999999999.99999999"),
            total_value=Decimal("99999999999999.99"),
        )
        conn.commit()

        qty = conn.scalar(
            text(
                "SELECT quantity FROM portfolio_draft_holdings "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert str(qty) == "999999999999.99999999"


def test_decimal_precision_unit_price_max_boundary(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(
            conn,
            pid,
            unit_price=Decimal("9999999999999999.9999"),
            total_value=Decimal("999999999999999999.99"),
        )
        conn.commit()

        price = conn.scalar(
            text(
                "SELECT unit_price FROM portfolio_draft_holdings "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert str(price) == "9999999999999999.9999"


def test_decimal_total_value_cents_precision(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(
            conn,
            pid,
            quantity=Decimal("1.5"),
            unit_price=Decimal("10.3333"),
            total_value=Decimal("15.50"),
        )
        conn.commit()

        total = conn.scalar(
            text(
                "SELECT total_value FROM portfolio_draft_holdings "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert str(total) == "15.50"


def test_draft_holdings_quantity_zero_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        assert_db_error(
            conn,
            "ck_portfolio_draft_holdings_quantity_positive",
            lambda: conn.execute(
                text(
                    "INSERT INTO portfolio_draft_holdings "
                    "(id, portfolio_id, asset_name, asset_category, quantity,"
                    " unit_price, total_value, valuation_date) "
                    "VALUES (:id, :pid, 'Zero Qty', 'test', 0, 1, 0, CURRENT_DATE)"
                ),
                {"id": uuid4(), "pid": pid},
            ),
        )


def test_draft_holdings_negative_price_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        assert_db_error(
            conn,
            "ck_portfolio_draft_holdings_price_nonnegative",
            lambda: conn.execute(
                text(
                    "INSERT INTO portfolio_draft_holdings "
                    "(id, portfolio_id, asset_name, asset_category, quantity,"
                    " unit_price, total_value, valuation_date) "
                    "VALUES (:id, :pid, 'Neg Price', 'test', 1, -1, 0, CURRENT_DATE)"
                ),
                {"id": uuid4(), "pid": pid},
            ),
        )


# ---------------------------------------------------------------------------
# Currency (household base_currency)
# ---------------------------------------------------------------------------


def test_currency_is_household_base_currency(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        currency = conn.scalar(
            text(
                "SELECT hp.base_currency FROM portfolios p "
                "JOIN household_profiles hp ON p.household_id = hp.id "
                "WHERE p.id = :pid"
            ),
            {"pid": pid},
        )
        assert currency == "USD"


def test_currency_format_enforced_on_household(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        assert_db_error(
            conn,
            "ck_household_profiles_currency_format",
            lambda: conn.execute(
                text(
                    "INSERT INTO household_profiles "
                    "(id, singleton_key, household_name, base_currency,"
                    " investment_horizon, liquidity_needs, risk_statement, notes) "
                    "VALUES (:id, true, 'Bad Currency', 'US', '', '', '', '')"
                ),
                {"id": uuid4()},
            ),
        )


# ---------------------------------------------------------------------------
# valuation_date <= CURRENT_DATE
# ---------------------------------------------------------------------------


def test_valuation_date_yesterday_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        yesterday = date.today() - timedelta(days=1)
        create_draft_holding(conn, pid, valuation_date=yesterday.isoformat())
        conn.commit()


def test_valuation_date_today_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(conn, pid)
        conn.commit()


def test_valuation_date_tomorrow_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))

        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        tomorrow = db_today + timedelta(days=1)
        assert_db_error(
            conn,
            "ck_portfolio_draft_holdings_valuation_date",
            lambda: conn.execute(
                text(
                    "INSERT INTO portfolio_draft_holdings "
                    "(id, portfolio_id, asset_name, asset_category, quantity,"
                    " unit_price, total_value, valuation_date) "
                    "VALUES (:id, :pid, 'Future', 'test', 1, 1, 1, CAST(:vd AS date))"
                ),
                {"id": uuid4(), "pid": pid, "vd": tomorrow.isoformat()},
            ),
        )


def test_snapshot_valuation_date_tomorrow_rejected(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db_today = conn.scalar(text("SELECT CURRENT_DATE"))

        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        tomorrow = db_today + timedelta(days=1)
        assert_db_error(
            conn,
            "ck_portfolio_snapshots_date",
            lambda: conn.execute(
                text(
                    "INSERT INTO portfolio_snapshots "
                    "(id, portfolio_id, version_number, valuation_date) "
                    "VALUES (:id, :pid, 1, CAST(:vd AS date))"
                ),
                {"id": uuid4(), "pid": pid, "vd": tomorrow.isoformat()},
            ),
        )


# ---------------------------------------------------------------------------
# Cash semantics
# ---------------------------------------------------------------------------


def test_cash_holding_category_cash_unit_price_one(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(
            conn,
            pid,
            asset_name="Operating Cash",
            asset_category="cash",
            quantity=Decimal("10000"),
            unit_price=Decimal("1.00"),
            total_value=Decimal("10000.00"),
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT asset_name, asset_category, quantity, unit_price, total_value "
                "FROM portfolio_draft_holdings WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        ).one()
        assert row.asset_name == "Operating Cash"
        assert row.asset_category == "cash"
        assert str(row.unit_price) == "1.0000"
        assert str(row.total_value) == "10000.00"


# ---------------------------------------------------------------------------
# Private asset
# ---------------------------------------------------------------------------


def test_private_asset_with_quantity_one(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        create_draft_holding(
            conn,
            pid,
            asset_name="Private Company X",
            asset_category="private",
            quantity=Decimal("1"),
            unit_price=Decimal("1000000"),
            total_value=Decimal("1000000.00"),
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT asset_category, quantity, unit_price "
                "FROM portfolio_draft_holdings WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        ).one()
        assert row.asset_category == "private"
        assert str(row.quantity) == "1.00000000"
        assert str(row.unit_price) == "1000000.0000"


# ---------------------------------------------------------------------------
# Zero holdings allowed (OD-S3-011 Option B)
# ---------------------------------------------------------------------------


def test_zero_draft_holdings_allowed(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        confirm_portfolio(conn, pid, holding_count=0)
        conn.commit()

        count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_snapshots "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert count == 1

        hc = conn.scalar(
            text(
                "SELECT holding_count FROM portfolio_snapshots "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert hc == 0


# ---------------------------------------------------------------------------
# Draft lifecycle: confirm + discard
# ---------------------------------------------------------------------------


def test_confirm_consumes_draft_and_sets_active(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        confirm_portfolio(conn, pid, holding_count=1)
        conn.commit()

        status = conn.scalar(
            text("SELECT status FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        assert status == "active"

        draft_count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_drafts "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert draft_count == 0

        holding_count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_draft_holdings "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert holding_count == 0

        snapshot_count = conn.scalar(
            text(
                "SELECT count(*) FROM portfolio_snapshots "
                "WHERE portfolio_id = :pid"
            ),
            {"pid": pid},
        )
        assert snapshot_count == 1


def test_discard_draft_before_any_confirm(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        conn.execute(
            text("DELETE FROM portfolio_draft_holdings WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolio_drafts WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        conn.commit()

        count = conn.scalar(
            text("SELECT count(*) FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        assert count == 0


# ---------------------------------------------------------------------------
# Snapshot immutability
# ---------------------------------------------------------------------------


def test_snapshot_insert_valid(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid, holding_count=1)
        conn.commit()

        vn = conn.scalar(
            text(
                "SELECT version_number FROM portfolio_snapshots "
                "WHERE id = :id"
            ),
            {"id": sid},
        )
        assert vn == 1


def test_snapshot_update_any_field_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

        assert_db_error(
            conn,
            'portfolio_snapshot_status_transition_forbidden',
            lambda: conn.execute(
                text(
                    "UPDATE portfolio_snapshots "
                    "SET notes = 'Changed' WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_snapshot_delete_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

        assert_db_error(
            conn,
            'portfolio_snapshot_delete_forbidden',
            lambda: conn.execute(
                text(
                    "DELETE FROM portfolio_snapshots WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_snapshot_multi_row_update_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)

        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        confirm_portfolio(conn, pid, holding_count=1)
        conn.commit()

        # Any UPDATE to portfolio_snapshots is rejected (single or multi-row)
        assert_db_error(
            conn,
            'portfolio_snapshot_status_transition_forbidden',
            lambda: conn.execute(
                text("UPDATE portfolio_snapshots SET notes = 'Mass update'")
            ),
        )


def test_snapshot_holding_update_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

        shid = insert_snapshot_holding(conn, sid)
        conn.commit()

        assert_db_error(
            conn,
            'portfolio_snapshot_holding_update_forbidden',
            lambda: conn.execute(
                text(
                    "UPDATE portfolio_snapshot_holdings "
                    "SET asset_name = 'Changed' WHERE id = :id"
                ),
                {"id": shid},
            ),
        )


def test_snapshot_holding_delete_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

        shid = insert_snapshot_holding(conn, sid)
        conn.commit()

        assert_db_error(
            conn,
            "portfolio_snapshot_holding_delete_forbidden",
            lambda: conn.execute(
                text(
                    "DELETE FROM portfolio_snapshot_holdings WHERE id = :id"
                ),
                {"id": shid},
            ),
        )


# ---------------------------------------------------------------------------
# Trigger function existence and properties
# ---------------------------------------------------------------------------


def test_snapshot_immutability_function_exists(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        count = conn.scalar(
            text(
                "SELECT count(*) FROM pg_proc "
                "WHERE proname = 'fn_portfolio_snapshot_immutability'"
            ),
        )
        assert count == 1


def test_snapshot_holdings_immutability_function_exists(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        count = conn.scalar(
            text(
                "SELECT count(*) FROM pg_proc "
                "WHERE proname = 'fn_portfolio_snapshot_holdings_immutability'"
            ),
        )
        assert count == 1


def test_portfolio_lifecycle_function_exists(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        count = conn.scalar(
            text(
                "SELECT count(*) FROM pg_proc "
                "WHERE proname = 'fn_portfolio_lifecycle'"
            ),
        )
        assert count == 1


def test_current_snapshot_deferred_trigger_exists(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT tgdeferrable, tginitdeferred FROM pg_trigger "
                "WHERE tgname = 'trg_portfolio_current_snapshot' "
                "AND NOT tgisinternal"
            ),
        ).one()
        assert row.tgdeferrable is True
        assert row.tginitdeferred is True


# ---------------------------------------------------------------------------
# Deferred constraint: at most one current snapshot per portfolio
# ---------------------------------------------------------------------------


def test_at_most_one_current_snapshot(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        # Insert two snapshots with status='current' in same transaction
        conn.execute(
            text(
                "INSERT INTO portfolio_snapshots "
                "(id, portfolio_id, version_number, status, valuation_date) "
                "VALUES (:id, :pid, 1, 'current', CURRENT_DATE)"
            ),
            {"id": uuid4(), "pid": pid},
        )
        conn.execute(
            text(
                "INSERT INTO portfolio_snapshots "
                "(id, portfolio_id, version_number, status, valuation_date) "
                "VALUES (:id, :pid, 2, 'current', CURRENT_DATE)"
            ),
            {"id": uuid4(), "pid": pid},
        )
        # Delete draft to satisfy deferred consistency trigger
        conn.execute(
            text("DELETE FROM portfolio_draft_holdings WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolio_drafts WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("UPDATE portfolios SET status = 'active' WHERE id = :pid"),
            {"pid": pid},
        )

        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "portfolio_multiple_current_snapshots" in str(exc.value)
        conn.rollback()


# ---------------------------------------------------------------------------
# Bypass regression (cross-transaction)
# ---------------------------------------------------------------------------


def test_snapshot_update_cross_transaction_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    # Transaction 1: Create confirmed snapshot
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

    # Transaction 2: Try to bypass immutability
    with postgres_engine.connect() as conn:
        assert_db_error(
            conn,
            'portfolio_snapshot_status_transition_forbidden',
            lambda: conn.execute(
                text(
                    "UPDATE portfolio_snapshots "
                    "SET valuation_date = '2020-01-01'::date WHERE id = :id"
                ),
                {"id": sid},
            ),
        )


def test_snapshot_delete_cross_transaction_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    # Transaction 1: Create confirmed snapshot
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        sid = confirm_portfolio(conn, pid)
        conn.commit()

    # Transaction 2: Try to bypass immutability
    with postgres_engine.connect() as conn:
        assert_db_error(
            conn,
            'portfolio_snapshot_delete_forbidden',
            lambda: conn.execute(
                text("DELETE FROM portfolio_snapshots WHERE id = :id"),
                {"id": sid},
            ),
        )


def test_draft_consistency_draft_status_without_draft_row_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = uuid4()
        conn.execute(
            text(
                "INSERT INTO portfolios (id, household_id, status) "
                "VALUES (:id, :hid, 'draft')"
            ),
            {"id": pid, "hid": hid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "portfolio_draft_requires_draft_row" in str(exc.value)
        conn.rollback()


def test_draft_consistency_active_with_draft_fails(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        create_draft_holding(conn, pid)
        conn.commit()

        # Try to set active while draft still exists
        conn.execute(
            text("UPDATE portfolios SET status = 'active' WHERE id = :pid"),
            {"pid": pid},
        )
        with pytest.raises(Exception) as exc:
            conn.commit()
        assert "portfolio_active_cannot_have_draft" in str(exc.value)
        conn.rollback()


# ---------------------------------------------------------------------------
# AuditEvent compatibility
# ---------------------------------------------------------------------------


def test_audit_event_for_portfolio(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        event_id = uuid4()
        conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                "VALUES (:id, :hid, 'local-owner', 'portfolio.draft.created', "
                "'Portfolio', :pid, CAST('{}' AS jsonb))"
            ),
            {"id": event_id, "hid": hid, "pid": pid},
        )
        conn.commit()

        row = conn.execute(
            text(
                "SELECT action, entity_type, entity_id, sequence_number "
                "FROM audit_events WHERE id = :id"
            ),
            {"id": event_id},
        ).one()
        assert row.action == "portfolio.draft.created"
        assert row.entity_type == "Portfolio"
        assert str(row.entity_id) == pid
        assert row.sequence_number is not None


def test_audit_event_stable_on_portfolio_discard(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        event_id = uuid4()
        conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                "VALUES (:id, :hid, 'local-owner', 'portfolio.draft.created', "
                "'Portfolio', :pid, CAST('{}' AS jsonb))"
            ),
            {"id": event_id, "hid": hid, "pid": pid},
        )
        conn.commit()

        # Discard portfolio
        conn.execute(
            text("DELETE FROM portfolio_draft_holdings WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolio_drafts WHERE portfolio_id = :pid"),
            {"pid": pid},
        )
        conn.execute(
            text("DELETE FROM portfolios WHERE id = :pid"),
            {"pid": pid},
        )
        conn.commit()

        # Audit event persists
        event_count = conn.scalar(
            text("SELECT count(*) FROM audit_events WHERE id = :id"),
            {"id": event_id},
        )
        assert event_count == 1


def test_audit_event_sequence_number_monotonic(
    db_session: Session,
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as conn:
        hid = create_household(conn)
        pid = create_portfolio_with_draft(conn, hid)
        conn.commit()

        conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                "VALUES (:id, :hid, 'local-owner', 'portfolio.draft.created', "
                "'Portfolio', :pid, CAST('{}' AS jsonb))"
            ),
            {"id": uuid4(), "hid": hid, "pid": pid},
        )
        conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                "VALUES (:id, :hid, 'local-owner', 'portfolio.snapshot.confirmed', "
                "'Portfolio', :pid, CAST('{}' AS jsonb))"
            ),
            {"id": uuid4(), "hid": hid, "pid": pid},
        )
        conn.commit()

        rows = conn.execute(
            text(
                "SELECT sequence_number FROM audit_events "
                "WHERE household_id = :hid "
                "ORDER BY sequence_number"
            ),
            {"hid": hid},
        ).all()
        assert len(rows) == 2
        assert rows[0].sequence_number < rows[1].sequence_number


# ---------------------------------------------------------------------------
# Expected constraints and FKs by table
# ---------------------------------------------------------------------------


EXPECTED_PORTFOLIO_CHECKS = {
    "portfolios": {
        "ck_portfolios_status",
    },
    "accounts": {
        "ck_accounts_name_length",
        "ck_accounts_sort_order_nonnegative",
    },
    "portfolio_drafts": {
        "ck_portfolio_drafts_revision_positive",
        "ck_portfolio_drafts_valuation_date",
    },
    "portfolio_draft_holdings": {
        "ck_portfolio_draft_holdings_quantity_positive",
        "ck_portfolio_draft_holdings_price_nonnegative",
        "ck_portfolio_draft_holdings_valuation_date",
        "ck_portfolio_draft_holdings_sort_order_nonnegative",
    },
    "portfolio_snapshots": {
        "ck_portfolio_snapshots_status",
        "ck_portfolio_snapshots_date",
        "ck_portfolio_snapshots_holding_count_nonnegative",
    },
    "portfolio_snapshot_holdings": {
        "ck_portfolio_snapshot_holdings_quantity_positive",
        "ck_portfolio_snapshot_holdings_price_nonnegative",
        "ck_portfolio_snapshot_holdings_sort_order_nonnegative",
    },
}

EXPECTED_PORTFOLIO_FKS = {
    "portfolios": {
        "fk_portfolios_household_id_household_profiles",
    },
    "accounts": {
        "fk_accounts_portfolio_id_portfolios",
    },
    "portfolio_drafts": {
        "fk_portfolio_drafts_portfolio_id_portfolios",
    },
    "portfolio_draft_holdings": {
        "fk_portfolio_draft_holdings_portfolio_id_drafts",
        "fk_portfolio_draft_holdings_account_id_accounts",
    },
    "portfolio_snapshots": {
        "fk_portfolio_snapshots_portfolio_id_portfolios",
    },
    "portfolio_snapshot_holdings": {
        "fk_portfolio_snapshot_holdings_snapshot_id_snapshots",
    },
}
