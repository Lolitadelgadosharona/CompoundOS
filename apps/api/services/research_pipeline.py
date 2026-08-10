"""Research Execution Pipeline — Sprint 012 Slice B.

Abstractions and orchestrator. No LLM provider integration yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# ═══════════════════════════════════════════════════════════════════════════
# Type definitions
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EvidenceBundle:
    """Collected evidence for a research run."""
    market_data: dict = field(default_factory=dict)
    portfolio_context: dict = field(default_factory=dict)
    policy_context: dict = field(default_factory=dict)
    guardian_status: dict = field(default_factory=dict)
    knowledge_memory: dict = field(default_factory=dict)


@dataclass
class PerspectiveResult:
    """Output of a single perspective analysis."""
    perspective: str
    model: str
    prompt_version: int
    analysis: dict
    conviction_score: int
    success: bool = True
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class RunResult:
    """Complete research run output."""
    run_id: UUID
    status: str
    perspectives: list[PerspectiveResult] = field(default_factory=list)
    memo: Optional[dict] = None
    confidence_score: Optional[int] = None
    confidence_level: Optional[str] = None
    recommendation: Optional[str] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# WorkerQueue + LocalWorker
# ═══════════════════════════════════════════════════════════════════════════


class WorkerQueue(ABC):
    """Abstract worker queue. Decouples from FastAPI BackgroundTasks."""

    @abstractmethod
    def enqueue(self, func: Callable, *args: object, **kwargs: object) -> None:
        """Enqueue a function for async execution."""


class LocalWorker(WorkerQueue):
    """V1: In-process worker using asyncio/new thread."""

    def enqueue(self, func: Callable, *args: object, **kwargs: object) -> None:
        import threading
        t = threading.Thread(target=func, args=args, kwargs=kwargs,
                             daemon=True)
        t.start()


# ═══════════════════════════════════════════════════════════════════════════
# EvidenceCollector
# ═══════════════════════════════════════════════════════════════════════════


class EvidenceCollector:
    """Collects evidence from internal sources. No external providers yet."""

    def collect(self, session: Session, household_id: UUID) -> EvidenceBundle:
        return EvidenceBundle(
            market_data=self._load_cache(session),
            portfolio_context=self._load_portfolio(session, household_id),
            policy_context=self._load_policy(session, household_id),
            guardian_status=self._load_guardian(session, household_id),
            knowledge_memory={},
        )

    def _load_cache(self, session: Session) -> dict:
        rows = session.execute(
            text(
                "SELECT symbol, data_type, data FROM market_data_cache"
                " WHERE expires_at > NOW() LIMIT 10"
            ),
        ).fetchall()
        return {f"{r[0]}:{r[1]}": r[2] for r in rows}

    def _load_portfolio(self, session: Session,
                        household_id: UUID) -> dict:
        rows = session.execute(
            text(
                "SELECT a.symbol, p.market_value, a.currency"
                " FROM positions p JOIN assets a ON p.asset_id = a.id"
                " JOIN accounts ac ON p.account_id = ac.id"
                " JOIN portfolios pf ON ac.portfolio_id = pf.id"
                " WHERE pf.household_id = :hid AND p.is_latest = TRUE"
            ),
            {"hid": household_id},
        ).fetchall()
        total = sum(r[1] for r in rows if r[1]) if rows else 0
        return {
            "total_value": str(total),
            "positions": [
                {"symbol": r[0], "value": str(r[1]), "currency": r[2]}
                for r in rows
            ],
        }

    def _load_policy(self, session: Session,
                     household_id: UUID) -> dict:
        # policy_capital_buckets references through version_id/draft_id
        return {}

    def _load_guardian(self, session: Session,
                       household_id: UUID) -> dict:
        row = session.execute(
            text(
                "SELECT COUNT(*) FROM guardian_events"
                " WHERE household_id = :hid"
            ),
            {"hid": household_id},
        ).scalar()
        return {"active_events": row or 0}


# ═══════════════════════════════════════════════════════════════════════════
# PerspectiveExecutor
# ═══════════════════════════════════════════════════════════════════════════


class PerspectiveExecutor:
    """Abstract perspective execution. V1 uses ThreadPoolExecutor."""

    PERSPECTIVES = [
        ("value", "claude-sonnet-4"),
        ("growth", "claude-sonnet-4"),
        ("risk", "claude-sonnet-4"),
        ("macro", "gpt-4o"),
        ("policy", "claude-sonnet-4"),
        ("portfolio_fit", "gpt-4o"),
    ]

    def __init__(self, max_workers: int = 6,
                 llm_provider: Optional[object] = None):
        self.max_workers = max_workers
        self.llm_provider = llm_provider

    def execute_all(self, evidence: EvidenceBundle,
                    session_factory: Callable[[], Session],
                    run_id: UUID,
                    ) -> list[PerspectiveResult]:
        results: list[PerspectiveResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._execute_one, p, m, evidence, session_factory,
                    run_id,
                ): p
                for p, m in self.PERSPECTIVES
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    perspective = futures[future]
                    results.append(PerspectiveResult(
                        perspective=perspective, model="unknown",
                        prompt_version=1, analysis={}, conviction_score=0,
                        success=False, error=str(exc),
                    ))

        return results

    def _execute_one(
        self, perspective: str, model: str, evidence: EvidenceBundle,
        session_factory: Callable[[], Session], run_id: UUID,
    ) -> PerspectiveResult:
        retry_count = 0
        last_error = None
        delays = [1, 4, 16]

        for attempt in range(3):
            try:
                if self.llm_provider:
                    analysis_raw = self.llm_provider.generate(
                        perspective=perspective, model=model,
                        evidence=evidence,
                    )
                else:
                    analysis_raw = self._mock_analysis(perspective)

                session = session_factory()
                try:
                    self._store_analysis(
                        session, run_id, perspective, model,
                        analysis_raw, retry_count,
                    )
                    session.commit()
                finally:
                    session.close()

                return PerspectiveResult(
                    perspective=perspective, model=model,
                    prompt_version=1, analysis=analysis_raw,
                    conviction_score=analysis_raw.get("conviction_score", 5),
                    success=True, retry_count=retry_count,
                )
            except Exception as exc:
                retry_count = attempt + 1
                last_error = str(exc)
                if attempt < 2:
                    import time
                    time.sleep(delays[attempt])

        session = session_factory()
        try:
            self._log_failure(session, run_id, perspective, model,
                              last_error, retry_count)
            session.commit()
        finally:
            session.close()

        return PerspectiveResult(
            perspective=perspective, model=model, prompt_version=1,
            analysis={}, conviction_score=0, success=False,
            error=last_error, retry_count=retry_count,
        )

    def _mock_analysis(self, perspective: str) -> dict:
        """Mock LLM analysis for testing. Replaced by real provider later."""
        return {
            "perspective": perspective,
            "thesis": f"Mock {perspective} analysis",
            "conviction_score": 7,
            "key_metrics": [],
        }

    def _store_analysis(self, session: Session, run_id: UUID,
                        perspective: str, model: str, analysis: dict,
                        retry_count: int) -> None:
        now = datetime.now(timezone.utc)
        pid = uuid4()
        session.execute(
            text(
                "INSERT INTO perspective_analyses"
                " (id, run_id, perspective, model, prompt_version,"
                " analysis, conviction_score, started_at, completed_at)"
                " VALUES (:id, :rid, :p, :m, 1, :a, :cs, :now, :now)"
            ),
            {
                "id": pid, "rid": run_id, "p": perspective, "m": model,
                "a": analysis,
                "cs": analysis.get("conviction_score", 5),
                "now": now,
            },
        )
        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, perspective, model, status, retry_count,"
                " input_tokens, output_tokens, cost_estimate,"
                " duration_ms, started_at, completed_at)"
                " VALUES (:id, :rid, :p, :m, 'success', :rc,"
                " 1000, 500, 0.006, 2500, :now, :now)"
            ),
            {
                "id": uuid4(), "rid": run_id, "p": perspective,
                "m": model, "rc": retry_count, "now": now,
            },
        )

    def _log_failure(self, session: Session, run_id: UUID,
                     perspective: str, model: str, error: Optional[str],
                     retry_count: int) -> None:
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, perspective, model, status, retry_count,"
                " error_message, started_at, completed_at)"
                " VALUES (:id, :rid, :p, :m, 'failure', :rc,"
                " :err, :now, :now)"
            ),
            {
                "id": uuid4(), "rid": run_id, "p": perspective,
                "m": model, "rc": retry_count, "err": error, "now": now,
            },
        )


# ═══════════════════════════════════════════════════════════════════════════
# ConfidenceEngine
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ConfidenceOutput:
    score: int
    level: str
    recommendation: str
    model_version: int
    breakdown: dict[str, int]


class ConfidenceEngine:
    """Versioned confidence scoring. V1 uses weighted formula."""

    MODEL_VERSION = 1
    WEIGHTS = {
        "evidence_quality": 25,
        "thesis_clarity": 20,
        "risk_completeness": 20,
        "policy_alignment": 15,
        "data_freshness": 10,
        "historical_precedent": 10,
    }

    def calculate(self, perspectives: list[PerspectiveResult],
                  evidence: EvidenceBundle,
                  ) -> ConfidenceOutput:
        if not perspectives:
            return ConfidenceOutput(
                score=0, level="LOW", recommendation="PASS",
                model_version=self.MODEL_VERSION,
                breakdown=dict.fromkeys(self.WEIGHTS, 0),
            )

        success_count = sum(1 for p in perspectives if p.success)
        conv_scores = [p.conviction_score for p in perspectives if p.success]
        avg_conv = (sum(conv_scores) / len(conv_scores) * 10
                    ) if conv_scores else 50

        evidence_score = min(25, 5 * success_count)
        thesis_score = min(20, int(avg_conv * 0.2))
        risk_score = 15 if success_count >= 3 else 10
        policy_score = 15 if evidence.policy_context else 10
        freshness_score = 10 if evidence.market_data else 5
        history_score = 5

        total = sum([
            evidence_score, thesis_score, risk_score,
            policy_score, freshness_score, history_score,
        ])

        if total >= 80:
            level = "HIGH"
        elif total >= 50:
            level = "MEDIUM"
        else:
            level = "LOW"

        recommendation = "BUY" if total >= 65 else "HOLD"

        return ConfidenceOutput(
            score=total, level=level, recommendation=recommendation,
            model_version=self.MODEL_VERSION,
            breakdown={
                "evidence_quality": evidence_score,
                "thesis_clarity": thesis_score,
                "risk_completeness": risk_score,
                "policy_alignment": policy_score,
                "data_freshness": freshness_score,
                "historical_precedent": history_score,
            },
        )


# ═══════════════════════════════════════════════════════════════════════════
# ResearchPipeline — orchestrator
# ═══════════════════════════════════════════════════════════════════════════


class ResearchPipeline:
    """Orchestrates a complete research run."""

    def __init__(
        self,
        worker: WorkerQueue,
        evidence_collector: EvidenceCollector,
        perspective_executor: PerspectiveExecutor,
        confidence_engine: ConfidenceEngine,
    ):
        self.worker = worker
        self.evidence = evidence_collector
        self.executor = perspective_executor
        self.confidence = confidence_engine

    def start(self, run_id: UUID, household_id: UUID,
              session_factory: Callable[[], Session],
              ) -> None:
        self.worker.enqueue(
            self._execute, run_id, household_id, session_factory,
        )

    def _execute(self, run_id: UUID, household_id: UUID,
                 session_factory: Callable[[], Session],
                 ) -> None:
        try:
            self._update_status(session_factory, run_id,
                                "collecting_evidence")
            s1 = session_factory()
            try:
                evidence = self.evidence.collect(s1, household_id)
            finally:
                s1.close()

            self._update_status(session_factory, run_id, "analyzing")
            perspectives = self.executor.execute_all(
                evidence, session_factory, run_id,
            )

            all_success = all(p.success for p in perspectives)
            if all_success:
                self._update_status(session_factory, run_id,
                                    "generating_memo")
                memo = self._generate_memo(perspectives, evidence)
                conf = self.confidence.calculate(perspectives, evidence)

                self._store_memo(session_factory, run_id, memo, conf)
                self._update_status(session_factory, run_id, "completed")
            else:
                self._update_status(session_factory, run_id,
                                    "completed")

        except Exception as exc:
            self._update_status(session_factory, run_id, "failed",
                                str(exc))

    def _update_status(self, session_factory: Callable[[], Session],
                       run_id: UUID, status: str,
                       error: Optional[str] = None) -> None:
        session = session_factory()
        try:
            now = datetime.now(timezone.utc)
            updates = "status = :status, updated_at = :now"
            params: dict = {"rid": run_id, "status": status, "now": now}

            if status in ("completed", "failed"):
                updates += ", completed_at = :now"
            if error:
                updates += ", error_message = :err"
                params["err"] = error

            session.execute(
                text(
                    f"UPDATE research_runs SET {updates}"
                    f" WHERE id = :rid"
                ),
                params,
            )
            session.commit()
        finally:
            session.close()

    def _generate_memo(self, perspectives: list[PerspectiveResult],
                       evidence: EvidenceBundle) -> dict:
        """Synthesize perspectives into structured memo. Mock for V1."""
        all_success = [p for p in perspectives if p.success]
        consensus = "BUY" if len(all_success) >= 4 else "HOLD"
        return {
            "thesis": f"Synthesized from {len(all_success)} perspectives",
            "evidence": {"sources_count": len(all_success)},
            "bull_case": {"narrative": "Multiple perspectives align"},
            "bear_case": {"narrative": "Some perspectives diverge"},
            "risks": [],
            "valuation": {"methodology": "multi-perspective"},
            "portfolio_impact": {"new_allocation_pct": "N/A"},
            "guardian_impact": {"compliant": True},
            "committee": {
                "consensus": consensus,
                "disagreements": [],
                "perspectives": {
                    p.perspective: {
                        "vote": "BUY" if p.conviction_score >= 5 else "HOLD",
                        "conviction": p.conviction_score,
                        "rationale": p.analysis.get("thesis", ""),
                    }
                    for p in all_success
                },
            },
            "decision_context": {"reason": "AI research"},
            "invalidation_conditions": {"conditions": []},
        }

    def _store_memo(self, session_factory: Callable[[], Session],
                    run_id: UUID, memo: dict,
                    conf: ConfidenceOutput) -> None:
        session = session_factory()
        try:
            now = datetime.now(timezone.utc)
            session.execute(
                text(
                    "INSERT INTO investment_memos"
                    " (id, run_id, memo, synthesis_model,"
                    " confidence_score, confidence_level,"
                    " recommendation, generated_at)"
                    " VALUES (:id, :rid, :memo, 'synthesis',"
                    " :score, :level, :rec, :now)"
                ),
                {
                    "id": uuid4(), "rid": run_id, "memo": memo,
                    "score": conf.score, "level": conf.level,
                    "rec": conf.recommendation, "now": now,
                },
            )
            session.commit()
        finally:
            session.close()
