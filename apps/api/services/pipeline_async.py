"""Async pipeline service — Sprint 015 Slice C.

FastAPI BackgroundTasks-based research execution with progress
tracking. 7 progress states from pending → complete/failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


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


async def execute_pipeline(run_id: UUID, symbol: str) -> None:
    """Simulated pipeline execution with progress tracking.

    In production, this calls ResearchIntelligencePipeline.execute().
    For Sprint 015, it simulates the 7-state progression with realistic
    timing.

    This function is designed to be passed to FastAPI BackgroundTasks.
    """
    import asyncio

    tracker = PipelineProgressTracker

    # 1. Collecting evidence
    tracker.update(run_id, PipelineState.COLLECTING)
    tracker.add_step(run_id, "Fetching market data")
    await asyncio.sleep(1)  # Simulate network call

    # 2. Running 6 perspectives
    tracker.update(run_id, PipelineState.RUNNING, perspective_count=0)
    for i, p in enumerate(
        ["value", "growth", "risk", "macro", "policy", "portfolio_fit"]
    ):
        tracker.add_step(run_id, f"Analyzing {p} perspective...")
        await asyncio.sleep(0.5)  # Simulate LLM call
        tracker.update(
            run_id, PipelineState.RUNNING,
            perspective_count=i + 1,
        )

    # 3. Generating memo
    tracker.update(run_id, PipelineState.GENERATING)
    tracker.add_step(run_id, "Synthesizing investment memo")
    await asyncio.sleep(0.5)

    # 4. Calculating confidence
    tracker.update(run_id, PipelineState.SCORING)
    tracker.add_step(run_id, "Calibrating confidence score")
    await asyncio.sleep(0.3)

    # 5. Complete
    memo_id = uuid4()
    tracker.update(
        run_id, PipelineState.COMPLETE,
        memo_id=str(memo_id), confidence=72,
    )
    tracker.add_step(run_id, f"Memo ready: /memo/{memo_id}")
