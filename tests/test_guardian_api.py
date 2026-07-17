"""Guardian Slice B tests: pure evaluator + service integration + API."""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from apps.api.services.guardian_evaluator import (
    CheckInput,
    PolicyAllocation,
    PortfolioHolding,
    build_category_map,
    compute_total_value,
    evaluate_drift,
    evaluate_category_exposure,
    evaluate_staleness,
)
from apps.api.services.guardian import (
    create_guardian_check,
    confirm_guardian_check,
    discard_guardian_check,
    update_guardian_draft,
    evaluate_all_checks,
    evaluate_one_check,
    CheckNotFoundError,
    DraftConflictError,
    NameConflictError,
    InvalidCheckTypeFieldsError,
    ConfirmRequiresDraftError,
    DraftNotFoundError,
)

pytestmark = pytest.mark.postgres


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hid(session: Session) -> UUID:
    row = session.execute(
        text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    if row is None:
        hid = uuid4()
        session.execute(
            text(
                "INSERT INTO household_profiles"
                " (id, singleton_key, household_name, base_currency,"
                "  investment_horizon, liquidity_needs, risk_statement, notes)"
                " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"
            ),
            {"id": hid},
        )
        session.commit()
        return hid
    return row[0]


def _create_policy(session: Session, hid: UUID) -> UUID:
    pid = uuid4()
    pvid = uuid4()
    session.execute(
        text("INSERT INTO investment_policies (id, household_id) VALUES (:id, :hid)"),
        {"id": pid, "hid": hid},
    )
    session.execute(
        text(
            "INSERT INTO investment_policy_versions"
            " (id, policy_id, version_number, status, published_at,"
            " objectives, time_horizon, liquidity, diversification,"
            " contribution_policy, rebalancing_policy, prohibited_assets,"
            " leverage_policy, decision_process, notes)"
            " VALUES (:id, :pid, 1, 'published', NOW(),"
            " 'o','h','','','','','','','','')"
        ),
        {"id": pvid, "pid": pid},
    )
    session.execute(
        text(
            "INSERT INTO investment_policy_version_allocations"
            " (id, version_id, asset_class_name, normalized_asset_class_name, target_percentage, sort_order)"
            " VALUES (:id, :vid, 'Global Equity', 'global equity', 60.00, 0)"
        ),
        {"id": uuid4(), "vid": pvid},
    )
    # Seal after all allocations are inserted
    session.execute(
        text("UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"),
        {"id": pvid},
    )
    session.commit()
    return pvid


def _create_portfolio(session: Session, hid: UUID, equity_val: str = "0") -> UUID:
    pid = uuid4()
    sid = uuid4()
    session.execute(
        text("INSERT INTO portfolios (id, household_id, status) VALUES (:id, :hid, 'active')"),
        {"id": pid, "hid": hid},
    )
    session.execute(
        text(
            "INSERT INTO portfolio_snapshots"
            " (id, portfolio_id, version_number, status, valuation_date)"
            " VALUES (:id, :pid, 1, 'current', '2026-06-01')"
        ),
        {"id": sid, "pid": pid},
    )
    if Decimal(equity_val) > 0:
        session.execute(
            text(
                "INSERT INTO portfolio_snapshot_holdings"
                " (id, snapshot_id, asset_name, asset_category, quantity, unit_price, total_value, valuation_date, sort_order)"
                " VALUES (:id, :sid, 'VTI', 'Global Equity', '100', :price, :tv, '2026-06-01', 0)"
            ),
            {"id": uuid4(), "sid": sid, "price": equity_val, "tv": equity_val},
        )
    session.commit()
    return sid


# ---------------------------------------------------------------------------
# Pure unit tests — no DB
# ---------------------------------------------------------------------------


class TestPureEvaluator:
    """Pure evaluation functions — zero database access."""

    def test_drift_exceeded(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="drift", threshold_value=Decimal("5.00"),
            severity="info",
            target_category_norm="Global Equity",
            target_holding_category_norm="Global Equity",
        )
        allocs = [PolicyAllocation("Global Equity", "global equity", Decimal("60.00"))]
        cmap = {"global equity": Decimal("100000")}
        tv = Decimal("100000")
        r = evaluate_drift(chk, allocs, cmap, tv)
        assert r.exceeded is True
        assert r.drift_pp == Decimal("40.00")  # 100% - 60% = 40pp

    def test_drift_equal_threshold_no_event(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="drift", threshold_value=Decimal("40.00"),
            severity="info",
            target_category_norm="Global Equity",
            target_holding_category_norm="Global Equity",
        )
        allocs = [PolicyAllocation("Global Equity", "global equity", Decimal("60.00"))]
        cmap = {"global equity": Decimal("100000")}
        tv = Decimal("100000")
        r = evaluate_drift(chk, allocs, cmap, tv)
        assert r.exceeded is False  # equal → no event

    def test_staleness_exceeded(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="staleness", threshold_value=Decimal("1.00"),
            severity="info", staleness_days=10,
        )
        r = evaluate_staleness(chk, date(2026, 6, 1), date(2026, 7, 17))
        assert r.exceeded is True
        assert r.staleness_days_actual == 46

    def test_staleness_below_no_event(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="staleness", threshold_value=Decimal("1.00"),
            severity="info", staleness_days=100,
        )
        r = evaluate_staleness(chk, date(2026, 6, 1), date(2026, 7, 17))
        assert r.exceeded is False

    def test_category_exposure_exceeded(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="category_exposure", threshold_value=Decimal("50.00"),
            severity="info",
            target_holding_category_norm="Global Equity",
        )
        cmap = {"global equity": Decimal("80000")}
        tv = Decimal("100000")
        r = evaluate_category_exposure(chk, cmap, tv)
        assert r.exceeded is True
        assert r.exposure_pct == Decimal("80.00")

    def test_category_exposure_below_no_event(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="category_exposure", threshold_value=Decimal("90.00"),
            severity="info",
            target_holding_category_norm="Global Equity",
        )
        cmap = {"global equity": Decimal("80000")}
        tv = Decimal("100000")
        r = evaluate_category_exposure(chk, cmap, tv)
        assert r.exceeded is False

    def test_zero_total_value_no_div_by_zero(self) -> None:
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="drift", threshold_value=Decimal("5.00"),
            severity="info",
            target_category_norm="Global Equity",
            target_holding_category_norm="Global Equity",
        )
        allocs = [PolicyAllocation("Global Equity", "global equity", Decimal("60.00"))]
        cmap = {"global equity": Decimal("0")}
        r = evaluate_drift(chk, allocs, cmap, Decimal("0"))
        assert r.exceeded is False

    def test_nfkc_normalization_matches(self) -> None:
        """Category matching is case+NFKC insensitive."""
        chk = CheckInput(
            check_id="c1", check_version_id="cv1",
            check_type="drift", threshold_value=Decimal("5.00"),
            severity="info",
            target_category_norm="global equity",
            target_holding_category_norm="GLOBAL  EQUITY",
        )
        allocs = [PolicyAllocation("Global Equity", "global equity", Decimal("60.00"))]
        cmap = {"global equity": Decimal("100000")}
        r = evaluate_drift(chk, allocs, cmap, Decimal("100000"))
        assert r.exceeded is True  # 100% - 60% = 40pp > 5pp


# ---------------------------------------------------------------------------
# Service integration tests — real PostgreSQL
# ---------------------------------------------------------------------------


class TestGuardianLifecycle:
    """Create → update → confirm → discard (real DB)."""

    def test_create_drift_check(self, db_session: Session) -> None:
        hid = _hid(db_session)
        result = create_guardian_check(
            db_session, household_id=hid,
            name="  Equity Drift  ", check_type="drift",
            threshold_value=Decimal("5.00"),
            target_category="Global Equity",
            target_holding_category="Global Equity",
        )
        assert result["identity"]["canonical_name"] == "equity drift"
        assert result["identity"]["check_type"] == "drift"
        assert result["draft"]["threshold_value"] == "5.00"

    def test_name_uniqueness(self, db_session: Session) -> None:
        hid = _hid(db_session)
        create_guardian_check(
            db_session, household_id=hid, name="Unique",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="eq", target_holding_category="eq",
        )
        with pytest.raises(NameConflictError):
            create_guardian_check(
                db_session, household_id=hid, name="  unique  ",
                check_type="drift", threshold_value=Decimal("5.00"),
                target_category="eq", target_holding_category="eq",
            )

    def test_update_revision_conflict(self, db_session: Session) -> None:
        hid = _hid(db_session)
        result = create_guardian_check(
            db_session, household_id=hid, name="Conflict",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="eq", target_holding_category="eq",
        )
        with pytest.raises(DraftConflictError):
            update_guardian_draft(
                db_session, check_id=UUID(result["identity"]["id"]),
                expected_revision=999, threshold_value=Decimal("1.00"),
            )

    def test_confirm_draft(self, db_session: Session) -> None:
        hid = _hid(db_session)
        result = create_guardian_check(
            db_session, household_id=hid, name="Confirm",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="eq", target_holding_category="eq",
        )
        confirmed = confirm_guardian_check(
            db_session,
            check_id=UUID(result["identity"]["id"]),
            expected_revision=result["draft"]["expected_revision"],
        )
        assert confirmed["latest_version"]["version_number"] == 1
        assert confirmed["identity"]["status"] == "confirmed"

    def test_discard_never_confirmed(self, db_session: Session) -> None:
        hid = _hid(db_session)
        result = create_guardian_check(
            db_session, household_id=hid, name="DiscNever",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="eq", target_holding_category="eq",
        )
        cid = UUID(result["identity"]["id"])
        discard_guardian_check(db_session, cid)
        # Verify check no longer exists in DB
        from sqlalchemy import text
        row = db_session.execute(
            text("SELECT 1 FROM guardian_checks WHERE id = :cid"), {"cid": cid}
        ).fetchone()
        assert row is None

    def test_per_type_validation(self, db_session: Session) -> None:
        hid = _hid(db_session)
        with pytest.raises(InvalidCheckTypeFieldsError):
            create_guardian_check(
                db_session, household_id=hid, name="BadDrift",
                check_type="drift", threshold_value=Decimal("5.00"),
            )
        with pytest.raises(InvalidCheckTypeFieldsError):
            create_guardian_check(
                db_session, household_id=hid, name="BadStale",
                check_type="staleness", threshold_value=Decimal("1.00"),
            )


class TestGuardianEvaluation:
    """Evaluation engine tests — real PostgreSQL."""

    def test_no_policy_skip(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_portfolio(db_session, hid, "10000")
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["status"] == "skipped_no_published_policy"
        assert result["evaluation_run"]["events_created"] == 0

    def test_no_snapshot_skip(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["status"] == "skipped_no_portfolio_snapshot"

    def test_zero_value_skip(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "0")
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["status"] == "skipped_zero_total_value"

    def test_drift_exceeded(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        r = create_guardian_check(
            db_session, household_id=hid, name="Drift",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="Global Equity", target_holding_category="Global Equity",
        )
        confirm_guardian_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            expected_revision=r["draft"]["expected_revision"],
        )
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["events_created"] >= 1

    def test_staleness_exceeded(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "10000")
        r = create_guardian_check(
            db_session, household_id=hid, name="Stale",
            check_type="staleness", threshold_value=Decimal("1.00"),
            staleness_days=10,
        )
        confirm_guardian_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            expected_revision=r["draft"]["expected_revision"],
        )
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["events_created"] >= 1

    def test_staleness_below_no_event(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "10000")
        r = create_guardian_check(
            db_session, household_id=hid, name="StaleLow",
            check_type="staleness", threshold_value=Decimal("1.00"),
            staleness_days=100,
        )
        confirm_guardian_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            expected_revision=r["draft"]["expected_revision"],
        )
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert result["evaluation_run"]["events_created"] == 0

    def test_evaluate_one(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        r = create_guardian_check(
            db_session, household_id=hid, name="One",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="Global Equity", target_holding_category="Global Equity",
        )
        confirm_guardian_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            expected_revision=r["draft"]["expected_revision"],
        )
        result = evaluate_one_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            household_id=hid, as_of_date=date(2026, 7, 17),
        )
        assert result["evaluation_run"]["checks_evaluated"] == 1

    def test_dedup_no_duplicate_events(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        r = create_guardian_check(
            db_session, household_id=hid, name="Dedup",
            check_type="drift", threshold_value=Decimal("5.00"),
            target_category="Global Equity", target_holding_category="Global Equity",
        )
        confirm_guardian_check(
            db_session, check_id=UUID(r["identity"]["id"]),
            expected_revision=r["draft"]["expected_revision"],
        )
        r1 = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        r2 = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert r1["evaluation_run"]["events_created"] >= 1
        assert r2["evaluation_run"]["events_created"] == 0  # deduped
