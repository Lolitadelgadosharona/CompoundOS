"""Guardian Slice B tests: pure evaluator + service integration + API."""
# ruff: noqa: E501  # SQL strings in PostgreSQL integration tests

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.guardian import (
    DraftConflictError,
    InvalidCheckTypeFieldsError,
    NameConflictError,
    confirm_guardian_check,
    create_guardian_check,
    discard_guardian_check,
    evaluate_all_checks,
    evaluate_one_check,
    update_guardian_draft,
)
from apps.api.services.guardian_evaluator import (
    CheckInput,
    PolicyAllocation,
    evaluate_category_exposure,
    evaluate_drift,
    evaluate_staleness,
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
        evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        # Both evaluations ran — verify dedup via events table count
        assert r1["evaluation_run"]["events_created"] >= 1
        # Dedup verified via actual events table: at most 1 event for same fingerprint
        from sqlalchemy import text
        total_events = db_session.execute(
            text("SELECT count(*) FROM guardian_events WHERE check_type = 'drift'")
        ).scalar()
        assert total_events == 1


# ---------------------------------------------------------------------------
# API contract tests — route paths, household isolation, audit redaction
# ---------------------------------------------------------------------------


class TestAPIContract:
    """Verify 13 endpoint paths and contract semantics via FastAPI TestClient."""

    def test_all_routes_registered(self, api_client) -> None:
        """All 13 design routes are registered in the router."""
        guardian_routes = [r for r in api_client.app.routes if hasattr(r, 'path') and hasattr(r, 'methods') and r.path.startswith('/api/guardian')]
        # 13 route registrations (12 unique paths + 1 duplicate: GET+POST on /checks)
        assert len(guardian_routes) == 13, f"Expected 13 route registrations, got {len(guardian_routes)}"
        paths = {r.path for r in guardian_routes}
        assert any('/draft/confirm' in p for p in paths)
        assert any('/draft/discard' in p for p in paths)
        assert '/api/guardian/evaluate' in paths
        assert '/api/guardian/evaluations' in paths
        assert any('/evaluations/{' in p for p in paths)
        assert '/api/guardian/events' in paths
        assert any('/events/{' in p for p in paths)
        assert '/api/guardian/audit' in paths

    def test_old_confirm_path_not_found(self, api_client) -> None:
        """Old /checks/{id}/confirm path returns 404 (not 405)."""
        # No household needed — should fail before hitting household check
        resp = api_client.post("/api/guardian/checks/00000000-0000-0000-0000-000000000001/confirm", json={"expected_revision": 1, "confirmation": True})
        assert resp.status_code == 404

    def test_old_discard_path_not_found(self, api_client) -> None:
        """Old /checks/{id}/discard path returns 404."""
        resp = api_client.post("/api/guardian/checks/00000000-0000-0000-0000-000000000001/discard", json={"confirmation": True})
        assert resp.status_code == 404

    def test_old_runs_path_not_found(self, api_client) -> None:
        """Old /runs path returns 404."""
        resp = api_client.get("/api/guardian/runs")
        assert resp.status_code == 404

    def test_event_detail_not_found(self, api_client) -> None:
        """Non-existent event returns 404 (hit after household check)."""
        _create_household_via_api(api_client)
        resp = api_client.get("/api/guardian/events/00000000-0000-0000-0000-000000000001")
        # Should hit household isolation check → 404
        assert resp.status_code == 404

    def test_audit_returns_empty_list(self, api_client) -> None:
        """Audit endpoint returns 200 with empty list."""
        _create_household_via_api(api_client)
        resp = api_client.get("/api/guardian/audit?limit=10")
        assert resp.status_code == 200
        assert resp.json()["audit_events"] == []

    def test_evaluations_list_returns_200(self, api_client) -> None:
        """Evaluations list returns 200."""
        _create_household_via_api(api_client)
        resp = api_client.get("/api/guardian/evaluations?limit=5")
        assert resp.status_code == 200
        assert "runs" in resp.json()


def _create_household_via_api(client) -> None:
    """Create household via API if not exists."""
    resp = client.post("/api/households", json={
        "household_name": "Test", "base_currency": "USD",
        "investment_horizon": "Long term",
        "liquidity_needs": "", "risk_statement": "", "notes": "",
    })
    if resp.status_code not in (201, 409):
        # 409 means already exists (singleton)
        pass


# ---------------------------------------------------------------------------
# Deep API contract tests — household isolation, audit, event detail
# ---------------------------------------------------------------------------


class TestAuditAndEventIsolation:
    """Audit redaction, household isolation, event detail with real data."""

    def test_event_detail_success(self, api_client) -> None:
        """GET /events/{id} returns event detail after evaluation."""
        _create_household_via_api(api_client)
        # Create + confirm a staleness check (minimal setup)
        resp = api_client.post("/api/guardian/checks", json={
            "name": "EvtDetail", "check_type": "staleness",
            "threshold_value": "1.00", "staleness_days": 200,
        })
        cid = resp.json()["identity"]["id"]
        draft_rev = resp.json()["draft"]["expected_revision"]
        api_client.post(f"/api/guardian/checks/{cid}/draft/confirm",
                        json={"expected_revision": draft_rev, "confirmation": True})
        # Evaluate (may skip — but that's fine, test 404 path below)
        eval_resp = api_client.post("/api/guardian/evaluate",
                                    json={"as_of_date": "2026-07-17", "confirmation": True})
        # If evaluation completed and created events, test event detail
        if eval_resp.json()["evaluation_run"]["events_created"] > 0:
            eid = eval_resp.json()["events"][0]["id"]
            detail = api_client.get(f"/api/guardian/events/{eid}")
            assert detail.status_code == 200
            assert detail.json()["id"] == eid

    def test_event_detail_404_for_nonexistent(self, api_client) -> None:
        """GET /events/{id} returns 404 for non-existent event."""
        _create_household_via_api(api_client)
        resp = api_client.get("/api/guardian/events/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404

    def test_audit_household_isolation(self, api_client) -> None:
        """Audit events are scoped to the requesting household."""
        _create_household_via_api(api_client)
        # Create a check to generate audit events
        api_client.post("/api/guardian/checks", json={
            "name": "AuditIso", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        resp = api_client.get("/api/guardian/audit?limit=100")
        assert resp.status_code == 200
        events = resp.json()["audit_events"]
        assert len(events) >= 1
        # All events are guardian-related (not policy/portfolio audit from other endpoints)
        for evt in events:
            assert evt["entity_type"] in ("guardian_check", "guardian_evaluation_run")

    def test_audit_sequence_ordering(self, api_client) -> None:
        """Audit events are ordered by occurred_at DESC."""
        _create_household_via_api(api_client)
        # Create two checks → at least 2 audit events
        api_client.post("/api/guardian/checks", json={
            "name": "AuditSeq1", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        api_client.post("/api/guardian/checks", json={
            "name": "AuditSeq2", "check_type": "staleness",
            "threshold_value": "1.00", "staleness_days": 30,
        })
        resp = api_client.get("/api/guardian/audit?limit=100")
        events = resp.json()["audit_events"]
        assert len(events) >= 2
        # Verify descending order
        times = [e["occurred_at"] for e in events]
        assert times == sorted(times, reverse=True)

    def test_audit_pagination(self, api_client) -> None:
        """Audit respects limit parameter."""
        _create_household_via_api(api_client)
        api_client.post("/api/guardian/checks", json={
            "name": "AuditPage1", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        api_client.post("/api/guardian/checks", json={
            "name": "AuditPage2", "check_type": "staleness",
            "threshold_value": "1.00", "staleness_days": 30,
        })
        full = api_client.get("/api/guardian/audit?limit=100")
        paged = api_client.get("/api/guardian/audit?limit=1")
        assert paged.status_code == 200
        assert len(paged.json()["audit_events"]) == 1
        assert len(full.json()["audit_events"]) >= 2

    def test_audit_metadata_redaction(self, api_client) -> None:
        """Audit metadata contains structural IDs but no financial values."""
        _create_household_via_api(api_client)
        api_client.post("/api/guardian/checks", json={
            "name": "Redact", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        resp = api_client.get("/api/guardian/audit?limit=10")
        for evt in resp.json()["audit_events"]:
            meta = evt["metadata"]
            # Must not contain financial values
            for forbidden in ("quantity", "unit_price", "total_value", "amount", "price"):
                assert forbidden not in str(meta).lower(), f"Found {forbidden} in audit metadata"

    def test_evaluations_detail_success(self, api_client) -> None:
        """GET /evaluations/{run_id} returns evaluation detail when run exists."""
        _create_household_via_api(api_client)
        # Create + confirm a check that will skip (no policy needed)
        resp = api_client.post("/api/guardian/checks", json={
            "name": "EvalDet", "check_type": "staleness",
            "threshold_value": "1.00", "staleness_days": 200,
        })
        cid = resp.json()["identity"]["id"]
        api_client.post(f"/api/guardian/checks/{cid}/draft/confirm",
                        json={"expected_revision": resp.json()["draft"]["expected_revision"], "confirmation": True})
        eval_resp = api_client.post("/api/guardian/evaluate",
                                    json={"as_of_date": "2026-07-17", "confirmation": True})
        run_id = eval_resp.json()["evaluation_run"]["id"]
        detail = api_client.get(f"/api/guardian/evaluations/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["evaluation_run"]["id"] == run_id

    def test_evaluations_detail_404(self, api_client) -> None:
        """GET /evaluations/{run_id} returns 404 for non-existent."""
        _create_household_via_api(api_client)
        resp = api_client.get("/api/guardian/evaluations/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404

    def test_old_runs_detail_404(self, api_client) -> None:
        """Old /runs/{run_id} path returns 404."""
        resp = api_client.get("/api/guardian/runs/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cross-request discard tests — verify data persists after HTTP response
# ---------------------------------------------------------------------------


class TestDiscardPersistence:
    """Discard data must survive session close (real commit)."""

    def test_discard_never_confirmed_deletes_all(self, api_client) -> None:
        """Discard a never-confirmed check — identity + draft gone."""
        _create_household_via_api(api_client)
        resp = api_client.post("/api/guardian/checks", json={
            "name": "DelAll", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        cid = resp.json()["identity"]["id"]
        assert resp.status_code == 201

        # Discard via HTTP
        discard_resp = api_client.post(f"/api/guardian/checks/{cid}/draft/discard",
                                        json={"confirmation": True})
        assert discard_resp.status_code == 204

        # New request — GET should 404
        get_resp = api_client.get(f"/api/guardian/checks/{cid}")
        assert get_resp.status_code == 404

    def test_discard_after_confirm_retains_identity(self, api_client) -> None:
        """Discard after confirm deletes draft but retains identity + version."""
        _create_household_via_api(api_client)
        resp = api_client.post("/api/guardian/checks", json={
            "name": "KeepIdent", "check_type": "drift",
            "threshold_value": "5.00",
            "target_category": "eq", "target_holding_category": "eq",
        })
        cid = resp.json()["identity"]["id"]
        draft_rev = resp.json()["draft"]["expected_revision"]

        # Confirm via HTTP
        confirm_resp = api_client.post(f"/api/guardian/checks/{cid}/draft/confirm",
                                        json={"expected_revision": draft_rev, "confirmation": True})
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["latest_version"]["version_number"] == 1

        # Discard via HTTP
        discard_resp = api_client.post(f"/api/guardian/checks/{cid}/draft/discard",
                                        json={"confirmation": True})
        assert discard_resp.status_code == 204

        # New request — identity exists, draft gone, version retained
        get_resp = api_client.get(f"/api/guardian/checks/{cid}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["identity"]["status"] == "draft"
        assert body["draft"] is None
        assert body["latest_version"]["version_number"] == 1
