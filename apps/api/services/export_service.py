"""Sprint 007 Slice A — Owner Export service (JSON + CSV)."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from apps.api.models import (
    CommitteeSession,
    DecisionConfirmedSnapshot,
    ExportTask,
    HouseholdProfile,
    InvestmentPolicyVersion,
    PortfolioSnapshot,
)

EXPORT_DIR = Path.home() / ".compoundos" / "exports"


def ensure_export_dir() -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR


def run_export(
    session: Session,
    entity_type: str,
    format: str,
    household_id: UUID,
) -> ExportTask:
    dest = ensure_export_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = "csv" if format == "csv" else "json"
    file_path = dest / f"{entity_type}_{stamp}.{ext}"

    task = ExportTask(
        id=uuid4(),
        entity_type=entity_type,
        format=format,
        file_path=str(file_path),
        status="running",
        started_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    session.add(task)
    session.commit()

    try:
        rows, result = _extract(session, entity_type, household_id)
        if format == "json":
            _write_json(file_path, rows)
        else:
            _write_csv(file_path, rows)

        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.row_count = len(rows)
        session.commit()
        return task
    except Exception:
        task.status = "failed"
        task.completed_at = datetime.now(timezone.utc)
        session.commit()
        raise


def cleanup_exports(session: Session) -> int:
    """Remove expired export files. Returns count deleted."""
    now = datetime.now(timezone.utc)
    expired = (
        session.query(ExportTask)
        .filter(ExportTask.expires_at < now, ExportTask.status == "completed")
        .all()
    )
    count = 0
    for task in expired:
        try:
            os.unlink(task.file_path)
        except FileNotFoundError:
            pass
        session.delete(task)
        count += 1
    session.commit()
    return count


# ═══════════════════════════════════════════════════════════════════════════
# Internal
# ═══════════════════════════════════════════════════════════════════════════


def _extract(
    session: Session,
    entity_type: str,
    household_id: UUID,
) -> tuple[list[dict], dict]:
    """Extract data for export. Returns rows."""
    if entity_type == "household":
        h = session.query(HouseholdProfile).first()
        row = {
            "id": str(h.id), "name": h.household_name,
            "currency": h.base_currency, "horizon": h.investment_horizon,
        } if h else {}
        return [row], {}

    if entity_type == "policy":
        versions = (
            session.query(InvestmentPolicyVersion)
            .filter_by(household_id=household_id)
            .order_by(InvestmentPolicyVersion.version_number)
            .all()
        )
        return [
            {
                "id": str(v.id), "version": v.version_number,
                "sealed_at": v.sealed_at.isoformat() if v.sealed_at else None,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "objectives": v.objectives, "time_horizon": v.time_horizon,
            }
            for v in versions
        ], {}

    if entity_type == "portfolio":
        snapshots = (
            session.query(PortfolioSnapshot)
            .filter_by(household_id=household_id)
            .order_by(PortfolioSnapshot.id)
            .all()
        )
        return [
            {
                "id": str(s.id), "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,  # noqa: E501
                "valuation_date": s.valuation_date.isoformat() if s.valuation_date else None,
            }
            for s in snapshots
        ], {}

    if entity_type == "decisions":
        decisions = (
            session.query(DecisionConfirmedSnapshot)
            .filter_by(household_id=household_id)
            .order_by(DecisionConfirmedSnapshot.id)
            .all()
        )
        return [
            {
                "id": str(d.id), "decision_date": d.decision_date.isoformat() if d.decision_date else None,  # noqa: E501
                "title": d.title, "summary": d.summary,
            }
            for d in decisions
        ], {}

    if entity_type == "committee_sessions":
        sessions_q = (
            session.query(CommitteeSession)
            .filter_by(household_id=household_id)
            .order_by(CommitteeSession.created_at)
            .all()
        )
        return [
            {
                "id": str(s.id), "title": s.title, "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions_q
        ], {}

    return [], {}


def _write_json(path: Path, rows: list[dict]) -> None:
    tmp = Path(str(path) + ".tmp")
    try:
        with open(str(tmp), "w") as f:
            json.dump(rows, f, default=str, indent=2)
        os.rename(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        with open(str(path), "w") as f:
            f.write("")
        return
    tmp = Path(str(path) + ".tmp")
    try:
        with open(str(tmp), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        os.rename(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()
