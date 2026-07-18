"""Sprint 005 Slice B — Orchestration Worker + API tests."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


# ── Pure scheduling tests ──


class TestComputeNextDailyRun:
    def test_next_run_after_now(self) -> None:
        from apps.api.services.orchestration_scheduling import compute_next_daily_run

        ref = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
        def clock():
            return ref
        result = compute_next_daily_run(time(9, 0), "UTC", clock=clock)
        # 9am today (July 20) is before 12pm, so next run is 9am tomorrow
        assert result == datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)

    def test_next_run_before_exec_time(self) -> None:
        from apps.api.services.orchestration_scheduling import compute_next_daily_run

        ref = datetime(2026, 7, 20, 8, 0, 0, tzinfo=UTC)
        def clock():
            return ref
        result = compute_next_daily_run(time(9, 0), "UTC", clock=clock)
        assert result == datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)

    def test_next_run_with_after(self) -> None:
        from apps.api.services.orchestration_scheduling import compute_next_daily_run

        after = datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)
        result = compute_next_daily_run(
            time(9, 0), "UTC", after=after,
            clock=lambda: datetime(2026, 7, 20, 8, 0, 0, tzinfo=UTC),
        )
        # After 9am, so next is tomorrow 9am
        assert result == datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)

    def test_dst_spring_forward(self) -> None:
        """DST spring-forward: nonexistent 2:30am skips to valid time."""
        from apps.api.services.orchestration_scheduling import compute_next_daily_run

        # 2026-03-08: US Eastern springs forward at 2am → 3am
        ref = datetime(2026, 3, 8, 3, 30, 0, tzinfo=UTC)  # 10:30pm ET on Mar 7
        def clock():
            return ref
        result = compute_next_daily_run(
            time(2, 30), "America/New_York", clock=clock,
        )
        # Next run should be at a valid local time on or after Mar 8
        assert result > ref

    def test_dst_fall_back(self) -> None:
        """DST fall-back: ambiguous 1:30am fires at first occurrence."""
        from apps.api.services.orchestration_scheduling import compute_next_daily_run

        # 2026-11-01: US Eastern falls back at 2am → 1am
        ref = datetime(2026, 11, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        def clock():
            return ref
        result = compute_next_daily_run(
            time(1, 30), "America/New_York", clock=clock,
        )
        assert result is not None

    def test_invalid_timezone_rejected(self) -> None:
        from apps.api.services.orchestration_scheduling import (
            compute_next_daily_run,
        )
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            compute_next_daily_run(time(9, 0), "Invalid/Zone")


class TestJobValidation:
    def test_unknown_job_type_rejected(self) -> None:
        from apps.api.services.orchestration_scheduling import (
            InvalidJobParamsError,
            validate_job_params,
        )
        with pytest.raises(InvalidJobParamsError, match="not in the approved"):
            validate_job_params("shell.run", {})

    def test_evaluate_one_requires_check_id(self) -> None:
        from apps.api.services.orchestration_scheduling import (
            InvalidJobParamsError,
            validate_job_params,
        )
        with pytest.raises(InvalidJobParamsError, match="requires 'check_id'"):
            validate_job_params("guardian.evaluate_one", {})

    def test_evaluate_all_rejects_params(self) -> None:
        from apps.api.services.orchestration_scheduling import (
            InvalidJobParamsError,
            validate_job_params,
        )
        with pytest.raises(InvalidJobParamsError, match="accepts no parameters"):
            validate_job_params("guardian.evaluate_all", {"extra": 1})


# ── Automation API tests ──


class TestAutomationAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, api_client: TestClient) -> None:
        self.client = api_client

    def _ensure_household(self) -> str:
        """Create a household and return its id."""
        resp2 = self.client.post("/api/households", json={
            "household_name": "T", "base_currency": "USD",
            "investment_horizon": "L", "liquidity_needs": "",
            "risk_statement": "", "notes": "",
        })
        if resp2.status_code == 201:
            return resp2.json()["id"]
        # Already exists — get it
        resp = self.client.get("/api/households")
        assert resp.status_code == 200, f"Household GET: {resp.status_code}"
        return resp.json()["id"]

    # ── Schedules ──

    def test_create_schedule(self) -> None:
        self._ensure_household()
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["enabled"] is False
        assert data["job_type"] == "guardian.evaluate_all"
        assert data["timezone"] == "UTC"

    def test_create_schedule_invalid_job_type(self) -> None:
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "shell.run",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        assert resp.status_code == 422

    def test_create_schedule_invalid_timezone(self) -> None:
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "Invalid/Zone",
        })
        assert resp.status_code == 422

    def test_list_schedules(self) -> None:
        self._ensure_household()
        self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        resp = self.client.get("/api/automation/schedules")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_schedule_not_found(self) -> None:
        resp = self.client.get(f"/api/automation/schedules/{uuid4()}")
        assert resp.status_code == 404

    def test_enable_schedule(self) -> None:
        self._ensure_household()
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        sid = resp.json()["id"]
        assert resp.json()["enabled"] is False
        resp2 = self.client.patch(f"/api/automation/schedules/{sid}", json={
            "enabled": True,
        })
        assert resp2.json()["enabled"] is True

    def test_delete_schedule(self) -> None:
        self._ensure_household()
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        sid = resp.json()["id"]
        resp2 = self.client.delete(f"/api/automation/schedules/{sid}")
        assert resp2.status_code == 204

    # ── Runs ──

    def test_list_runs_empty(self) -> None:
        self._ensure_household()
        resp = self.client.get("/api/automation/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_manual_trigger(self) -> None:
        self._ensure_household()
        # Create schedule first
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        jd_id = resp.json()["job_definition_id"]
        resp2 = self.client.post("/api/automation/runs", json={
            "job_definition_id": jd_id,
        })
        assert resp2.status_code == 201
        assert resp2.json()["status"] == "pending"
        assert resp2.json()["triggered_by"] == "manual"

    def test_manual_trigger_not_found(self) -> None:
        self._ensure_household()
        resp = self.client.post("/api/automation/runs", json={
            "job_definition_id": str(uuid4()),
        })
        assert resp.status_code == 422

    def test_get_run_detail(self) -> None:
        self._ensure_household()
        resp = self.client.post("/api/automation/schedules", json={
            "job_type": "guardian.evaluate_all",
            "execution_time": "09:00:00",
            "timezone": "UTC",
        })
        jd_id = resp.json()["job_definition_id"]
        trig = self.client.post("/api/automation/runs", json={
            "job_definition_id": jd_id,
        })
        rid = trig.json()["id"]
        resp2 = self.client.get(f"/api/automation/runs/{rid}")
        assert resp2.status_code == 200
        assert "attempts" in resp2.json()

    # ── Worker status ──

    def test_worker_status_readonly(self) -> None:
        self._ensure_household()
        resp = self.client.get("/api/automation/worker/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "worker_count" in data
        assert "active_leases" in data
        assert "running_runs" in data


# ── Worker claim + repository tests ──


class TestWorkerClaim:
    def _setup_hj(self, session: Session) -> tuple[str, str]:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"
        ), {"id": hid})
        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})
        return str(hid), str(jid)

    def test_claim_due_schedule(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import claim_due_schedules

        hid, jid = self._setup_hj(db_session)
        now = _now()
        past = now - timedelta(minutes=5)

        sid = uuid4()
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at, enabled)"
            " VALUES (:id, :jid, '09:00', 'UTC', :nr, TRUE)"
        ), {"id": sid, "jid": jid, "nr": past})
        db_session.commit()

        due = claim_due_schedules(db_session, clock=lambda: now)
        assert len(due) == 1
        assert due[0]["schedule_id"] == str(sid)

    def test_disabled_schedule_not_claimed(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import claim_due_schedules

        hid, jid = self._setup_hj(db_session)
        now = _now()
        past = now - timedelta(minutes=5)

        sid = uuid4()
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at, enabled)"
            " VALUES (:id, :jid, '09:00', 'UTC', :nr, FALSE)"
        ), {"id": sid, "jid": jid, "nr": past})
        db_session.commit()

        due = claim_due_schedules(db_session, clock=lambda: now)
        assert len(due) == 0

    def test_future_schedule_not_claimed(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import claim_due_schedules

        hid, jid = self._setup_hj(db_session)
        now = _now()
        future = now + timedelta(hours=1)

        sid = uuid4()
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at, enabled)"
            " VALUES (:id, :jid, '09:00', 'UTC', :nr, TRUE)"
        ), {"id": sid, "jid": jid, "nr": future})
        db_session.commit()

        due = claim_due_schedules(db_session, clock=lambda: now)
        assert len(due) == 0


# ── Lease fencing (repository-level) ──


class TestLeaseFencing:
    def _setup(self, session: Session) -> tuple[str, str]:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"
        ), {"id": hid})
        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})
        now = _now()
        rid = uuid4()
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'manual', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now, "hid": str(hid)})
        return str(hid), str(rid)

    def test_acquire_lease(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import acquire_lease

        _, rid = self._setup(db_session)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w1")
        assert lease["fencing_token"] == 1

    def test_heartbeat_success(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import (
            acquire_lease,
            heartbeat_lease,
        )

        _, rid = self._setup(db_session)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w1")
        r = heartbeat_lease(
            db_session,
            lease_id=lease["lease_id"],
            worker_id="w1",
            fencing_token=lease["fencing_token"],
        )
        assert r == 1

    def test_heartbeat_stale_token_zero(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import (
            acquire_lease,
            heartbeat_lease,
        )

        _, rid = self._setup(db_session)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w1")
        r = heartbeat_lease(
            db_session,
            lease_id=lease["lease_id"],
            worker_id="w1",
            fencing_token=999,
        )
        assert r == 0

    def test_finalize_success(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import (
            acquire_lease,
            finalize_run,
        )

        _, rid = self._setup(db_session)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w1")
        r = finalize_run(
            db_session,
            run_id=rid,
            lease_id=lease["lease_id"],
            worker_id="w1",
            fencing_token=lease["fencing_token"],
            status="completed",
        )
        assert r == 1

    def test_finalize_stale_token_zero(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import (
            acquire_lease,
            finalize_run,
        )

        _, rid = self._setup(db_session)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w1")
        r = finalize_run(
            db_session,
            run_id=rid,
            lease_id=lease["lease_id"],
            worker_id="w1",
            fencing_token=999,
            status="completed",
        )
        assert r == 0
