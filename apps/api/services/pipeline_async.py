"""Async pipeline service — Sprint 015 Slice C.

FastAPI BackgroundTasks-based research execution with progress
tracking. 7 progress states from pending → complete/failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class PipelineState(str, Enum):
    PENDING = "pending"
    COLLECTING = "collecting_evidence"
    RUNNING = "running_perspectives"
    GENERATING = "generating_memo"
    SCORING = "calculating_confidence"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PipelineProgress:
    run_id: UUID
    state: PipelineState = PipelineState.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    memo_id: str | None = None
    confidence: int | None = None
    perspective_count: int = 0
    total_perspectives: int = 6
    steps: list[dict] = field(default_factory=list)

    @property
    def progress_pct(self) -> int:
        if self.state in (PipelineState.COMPLETE, PipelineState.FAILED):
            return 100
        if self.state == PipelineState.PENDING:
            return 0
        state_pcts = {
            PipelineState.COLLECTING: 15,
            PipelineState.RUNNING: 25 + self.perspective_count * 10,
            PipelineState.GENERATING: 85,
            PipelineState.SCORING: 95,
        }
        return state_pcts.get(self.state, 0)

    @property
    def is_complete(self) -> bool:
        return self.state == PipelineState.COMPLETE

    @property
    def is_failed(self) -> bool:
        return self.state == PipelineState.FAILED


class PipelineProgressTracker:
    """In-memory progress tracker for research pipelines.

    In production, this would be backed by Redis or the research_runs
    table. For Sprint 015, a simple in-memory dict is sufficient for
    the solo-Owner use case.
    """

    _runs: dict[UUID, PipelineProgress] = {}

    @classmethod
    def create(cls, run_id: UUID) -> PipelineProgress:
        progress = PipelineProgress(
            run_id=run_id,
            state=PipelineState.PENDING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        cls._runs[run_id] = progress
        return progress

    @classmethod
    def get(cls, run_id: UUID) -> PipelineProgress | None:
        return cls._runs.get(run_id)

    @classmethod
    def update(cls, run_id: UUID, state: PipelineState,
               **kwargs) -> PipelineProgress | None:
        progress = cls._runs.get(run_id)
        if progress is None:
            return None
        progress.state = state
        for k, v in kwargs.items():
            setattr(progress, k, v)
        if state in (PipelineState.COMPLETE, PipelineState.FAILED):
            progress.completed_at = datetime.now(timezone.utc).isoformat()
        return progress

    @classmethod
    def add_step(cls, run_id: UUID, step: str) -> None:
        progress = cls._runs.get(run_id)
        if progress:
            progress.steps.append({
                "step": step,
                "time": datetime.now(timezone.utc).isoformat(),
            })


async def execute_pipeline(run_id: UUID, symbol: str,
                           household_id: UUID) -> None:
    """Run the REAL ResearchIntelligencePipeline in a background task.

    Opens a fresh DB session — never holds the request session across
    async work. On success it wires the full M5-004 lifecycle:
    Research → Committee → Decision Draft (pending Owner approval).
    """
    import json

    from sqlalchemy import text

    from apps.api.database import SessionLocal
    from apps.api.services.decision_lifecycle import (
        CommitteeIntegrationService,
        DecisionBridgeService,
        _symbol_for_run,
    )
    from apps.api.services.research_pipeline_factory import (
        build_research_pipeline,
    )

    tracker = PipelineProgressTracker
    tracker.update(run_id, PipelineState.COLLECTING)
    tracker.add_step(run_id, "Collecting evidence")

    session = SessionLocal()
    try:
        pipeline = build_research_pipeline()
        tracker.update(run_id, PipelineState.RUNNING, perspective_count=0)
        tracker.add_step(run_id, "Running 6 perspectives")
        output = pipeline.execute(session, run_id, household_id, symbol)

        tracker.update(run_id, PipelineState.GENERATING)
        tracker.add_step(run_id, "Synthesizing memo")
        tracker.update(run_id, PipelineState.SCORING)
        tracker.add_step(run_id, "Calibrating confidence score")

        if output.memo is None:
            tracker.update(run_id, PipelineState.FAILED,
                           error="Memo generation failed")
            return

        # Research → Committee (M5-004)
        bridge = CommitteeIntegrationService.complete_research(
            session, run_id, household_id,
        )
        memo_id = bridge["memo_id"]

        # Committee → Decision Draft (pending Owner approval)
        memo_row = session.execute(
            text(
                "SELECT memo, recommendation FROM investment_memos"
                " WHERE id = :id"
            ),
            {"id": UUID(bridge["memo_id"])},
        ).fetchone()
        memo_json = (memo_row[0] if isinstance(memo_row[0], dict)
                     else json.loads(memo_row[0]))
        recommendation = memo_row[1] or "HOLD"
        decision, _draft = DecisionBridgeService.create_decision_draft(
            session, run_id, _symbol_for_run(session, run_id),
            recommendation, memo_json.get("thesis", ""),
            memo_json.get("risks", []),
        )

        tracker.update(
            run_id, PipelineState.COMPLETE,
            memo_id=str(memo_id),
            confidence=(output.confidence.score
                        if output.confidence else None),
        )
        tracker.add_step(run_id, f"Memo ready: /memo/{memo_id}")
        tracker.add_step(
            run_id, f"Pending decision: {decision.id}",
        )
    except Exception as exc:  # noqa: BLE001 — background worker boundary
        tracker.update(run_id, PipelineState.FAILED, error=str(exc))
    finally:
        session.close()

