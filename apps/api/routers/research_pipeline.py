"""Router for Sprint 012 Slice B — Research Execution Pipeline."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import SessionLocal, get_session
from apps.api.services.research_pipeline import (
    ConfidenceEngine,
    EvidenceCollector,
    LocalWorker,
    PerspectiveExecutor,
    ResearchPipeline,
)

router = APIRouter(prefix="/api/research", tags=["research"])


def _get_pipeline() -> ResearchPipeline:
    return ResearchPipeline(
        worker=LocalWorker(),
        evidence_collector=EvidenceCollector(),
        perspective_executor=PerspectiveExecutor(max_workers=6),
        confidence_engine=ConfidenceEngine(),
    )


def _session_factory() -> Session:
    return SessionLocal()


# ═══════════════════════════════════════════════════════════════════════
# POST /api/research/start  —  Start research execution
# ═══════════════════════════════════════════════════════════════════════


@router.post("/start")
def start_research(
    request_id: UUID,
    session: Session = Depends(get_session),
) -> dict:
    """Start AI research execution for a research request.

    Creates a new research_run and enqueues async execution.
    Returns the run_id immediately.
    """
    req = session.execute(
        text(
            "SELECT id, investment_idea_id, review_request_id"
            " FROM research_requests WHERE id = :rid"
        ),
        {"rid": request_id},
    ).fetchone()
    if req is None:
        raise HTTPException(404, "Research request not found")

    # Get household_id from investment_idea
    idea = session.execute(
        text(
            "SELECT household_id FROM investment_ideas"
            " WHERE id = :iid"
        ),
        {"iid": req[1]},
    ).fetchone()
    if idea is None:
        raise HTTPException(404, "Investment idea not found")

    # Determine next run_number
    max_run = session.execute(
        text(
            "SELECT COALESCE(MAX(run_number), 0)"
            " FROM research_runs WHERE request_id = :rid"
        ),
        {"rid": request_id},
    ).scalar()
    run_number = (max_run or 0) + 1
    from uuid import uuid4

    run_id = uuid4()
    session.execute(
        text(
            "INSERT INTO research_runs"
            " (id, request_id, run_number, status,"
            " created_at, updated_at)"
            " VALUES (:id, :req, :num, 'pending', NOW(), NOW())"
        ),
        {"id": run_id, "req": request_id, "num": run_number},
    )
    session.commit()

    pipeline = _get_pipeline()
    pipeline.start(run_id, idea[0], _session_factory)

    return {"run_id": str(run_id), "run_number": run_number,
            "status": "pending"}


# ═══════════════════════════════════════════════════════════════════════
# GET /api/research/{request_id}/progress  —  Progress for a request
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{request_id}/progress")
def get_progress(
    request_id: UUID,
    session: Session = Depends(get_session),
) -> dict:
    req = session.execute(
        text(
            "SELECT id FROM research_requests WHERE id = :rid"
        ),
        {"rid": request_id},
    ).fetchone()
    if req is None:
        raise HTTPException(404, "Research request not found")

    runs = session.execute(
        text(
            "SELECT id, run_number, status, started_at, completed_at,"
            " error_message"
            " FROM research_runs"
            " WHERE request_id = :rid ORDER BY run_number DESC"
        ),
        {"rid": request_id},
    ).fetchall()

    result: dict = {"request_id": str(request_id), "runs": []}
    for r in runs:
        run_data: dict = {
            "run_id": str(r[0]), "run_number": r[1], "status": r[2],
            "started_at": str(r[3]) if r[3] else None,
            "completed_at": str(r[4]) if r[4] else None,
            "error_message": r[5],
        }
        per_count = session.execute(
            text(
                "SELECT COUNT(*) FROM perspective_analyses"
                " WHERE run_id = :rid"
            ),
            {"rid": r[0]},
        ).scalar()
        run_data["perspectives_complete"] = per_count or 0
        result["runs"].append(run_data)

    return result


# ═══════════════════════════════════════════════════════════════════════
# GET /api/research/runs/{run_id}/results  —  Complete results
# ═══════════════════════════════════════════════════════════════════════


@router.get("/runs/{run_id}/results")
def get_results(
    run_id: UUID,
    session: Session = Depends(get_session),
) -> dict:
    run = session.execute(
        text(
            "SELECT id, status, error_message FROM research_runs"
            " WHERE id = :rid"
        ),
        {"rid": run_id},
    ).fetchone()
    if run is None:
        raise HTTPException(404, "Run not found")

    perspectives = session.execute(
        text(
            "SELECT perspective, model, analysis, conviction_score,"
            " completed_at"
            " FROM perspective_analyses WHERE run_id = :rid"
            " ORDER BY created_at"
        ),
        {"rid": run_id},
    ).fetchall()

    memo_row = session.execute(
        text(
            "SELECT memo, confidence_score, confidence_level,"
            " recommendation, synthesis_model, generated_at"
            " FROM investment_memos WHERE run_id = :rid"
        ),
        {"rid": run_id},
    ).fetchone()

    return {
        "run_id": str(run[0]),
        "status": run[1],
        "error": run[2],
        "perspectives": [
            {
                "perspective": p[0], "model": p[1],
                "analysis": p[2], "conviction_score": p[3],
                "completed_at": str(p[4]) if p[4] else None,
            }
            for p in perspectives
        ],
        "memo": (memo_row[0] if memo_row else None),
        "confidence_score": (memo_row[1] if memo_row else None),
        "confidence_level": (memo_row[2] if memo_row else None),
        "recommendation": (memo_row[3] if memo_row else None),
    }
