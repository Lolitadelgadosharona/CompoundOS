"""Dashboard research workflow — Sprint 014 Slice C.

Connects the dashboard to the real research pipeline.
Thin integration layer — delegates to existing services.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardResearchService:
    """Dashboard-facing research request service.

    Delegates all heavy lifting to Sprint 011-013 services.
    This layer only: creates research requests, tracks status,
    and returns displayable results.
    """

    @staticmethod
    def create_request(
        session: Session, symbol: str, household_id: UUID,
    ) -> dict:
        """Create a research request and initial run.

        The actual pipeline execution is async — this creates
        the request record and returns immediately. The dashboard
        polls for completion via get_status().
        """
        # Find or create investment idea
        idea_id = uuid4()
        session.execute(
            text(
                "INSERT INTO investment_ideas (id, household_id, title,"
                " status, source, confidence, created_at)"
                " VALUES (:id, :hh, :t, 'draft', 'owner', 'LOW', NOW())"
                " ON CONFLICT DO NOTHING"
            ),
            {"id": idea_id, "hh": household_id, "t": f"Research: {symbol}"},
        )

        # Create review request
        rr_id = uuid4()
        session.execute(
            text(
                "INSERT INTO committee_review_requests"
                " (id, investment_idea_id, status, requested_by, created_at)"
                " VALUES (:id, :iid, 'pending', 'owner', NOW())"
            ),
            {"id": rr_id, "iid": idea_id},
        )

        # Create research request
        req_id = uuid4()
        session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
            ),
            {"id": req_id, "rrid": rr_id},
        )

        # Create research run
        run_id = uuid4()
        session.execute(
            text(
                "INSERT INTO research_runs"
                " (id, request_id, run_number, status, created_at, updated_at)"
                " VALUES (:id, :req, 1, 'pending', NOW(), NOW())"
            ),
            {"id": run_id, "req": req_id},
        )

        session.commit()
        return {
            "request_id": str(req_id), "run_id": str(run_id),
            "symbol": symbol, "status": "pending",
        }

    @staticmethod
    def get_status(session: Session, run_id: UUID) -> dict:
        """Return the current status of a research run."""
        run = session.execute(
            text(
                "SELECT r.status, m.id AS memo_id, m.confidence_score,"
                " m.recommendation FROM research_runs r"
                " LEFT JOIN investment_memos m ON m.run_id = r.id"
                " WHERE r.id = :rid"
            ),
            {"rid": run_id},
        ).fetchone()
        if run is None:
            return {"status": "not_found"}
        return {
            "status": run[0],
            "memo_id": str(run[1]) if run[1] else None,
            "confidence": run[2],
            "recommendation": run[3],
        }

    @staticmethod
    def list_recent(session: Session, limit: int = 20) -> list[dict]:
        """List recent research runs for the dashboard."""
        rows = session.execute(
            text(
                "SELECT r.id, r.status, r.created_at,"
                " m.id AS memo_id, m.confidence_score"
                " FROM research_runs r"
                " LEFT JOIN investment_memos m ON m.run_id = r.id"
                " ORDER BY r.created_at DESC LIMIT :lim"
            ),
            {"lim": limit},
        ).fetchall()
        return [
            {
                "run_id": str(r[0]), "status": r[1],
                "date": str(r[2])[:10] if r[2] else None,
                "memo_id": str(r[3]) if r[3] else None,
                "confidence": r[4],
            }
            for r in rows
        ]
