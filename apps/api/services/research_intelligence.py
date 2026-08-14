"""Active Research Intelligence Loop — Sprint 013 Slice C.

MemoGenerator and pipeline integration. Wires EvidenceCollector,
PerspectiveExecutor, MemoGenerator, and ConfidenceEngine into a
complete end-to-end AI investment research workflow.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.llm_provider_runtime import (
    ExecutionResult,
    GovernedLLMExecutor,
)
from apps.api.services.research_evidence import EvidenceBundle

# ═══════════════════════════════════════════════════════════════════════════
# PerspectiveResult — output of a single perspective execution
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PerspectiveResult:
    perspective: str
    model: str
    provider: str
    analysis: dict
    conviction_score: int
    success: bool = True
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# MemoGenerator — synthesizes 6 perspectives into structured memo
# ═══════════════════════════════════════════════════════════════════════════


class MemoGenerator:
    """Synthesizes perspective analyses into 11-section Investment Memo.

    Uses governed LLM call (synthesis perspective) with structured prompt.
    Output validated against investment_memos schema.
    """

    REQUIRED_PERSPECTIVES = 6
    DEFAULT_MAX_OUTPUT_TOKENS = 8000

    def __init__(self, executor: GovernedLLMExecutor):
        self.executor = executor

    @staticmethod
    def resolve_max_output_tokens() -> int:
        """Return the memo synthesis output-token cap.

        Configurable via MEMO_MAX_OUTPUT_TOKENS (default 8000). Invalid or
        non-positive values fall back to the default so a bad env override
        can never silently truncate synthesis below a usable floor.
        """
        raw = os.environ.get("MEMO_MAX_OUTPUT_TOKENS", "").strip()
        if raw:
            try:
                value = int(raw)
            except ValueError:
                return MemoGenerator.DEFAULT_MAX_OUTPUT_TOKENS
            if value > 0:
                return value
        return MemoGenerator.DEFAULT_MAX_OUTPUT_TOKENS

    def generate(self, session: Session, run_id: UUID,
                 perspectives: list[PerspectiveResult],
                 evidence: EvidenceBundle,
                 ) -> Optional[dict]:
        if len([p for p in perspectives if p.success]) < self.REQUIRED_PERSPECTIVES:
            return None

        synthesis_prompt = self._build_synthesis_prompt(
            perspectives, evidence,
        )

        try:
            result = self.executor.execute(
                session, run_id, "synthesis",
                system_prompt=(
                    "You are the synthesis analyst for CompoundOS. "
                    "Synthesize the following investment perspectives "
                    "into a structured investment memo. Return valid JSON."
                ),
                user_prompt=synthesis_prompt,
                caller="ai",
                max_output_tokens=self.resolve_max_output_tokens(),
            )
        except Exception:
            return None

        return self._structure_memo(result.validated, perspectives,
                                    evidence)

    def _build_synthesis_prompt(self, perspectives,
                                evidence: EvidenceBundle) -> str:
        parts = []
        parts.append("Synthesize these analyses into an investment memo.")
        parts.append("")

        for p in perspectives:
            if p.success:
                parts.append(f"--- {p.perspective.upper()} ---")
                parts.append(json.dumps(p.analysis, indent=2))
                parts.append("")

        if evidence.market_data:
            parts.append("--- MARKET DATA ---")
            parts.append(json.dumps(evidence.market_data, indent=2))

        if evidence.missing_sources:
            parts.append("--- MISSING SOURCES ---")
            parts.append(", ".join(evidence.missing_sources))

        parts.append(
            "\nReturn a JSON object with: thesis, evidence, bull_case, "
            "bear_case, risks, valuation, portfolio_impact, "
            "guardian_impact, committee, decision_context, "
            "invalidation_conditions."
        )
        return "\n".join(parts)

    def _structure_memo(self, validated: dict,
                        perspectives: list[PerspectiveResult],
                        evidence: EvidenceBundle) -> dict:
        success = [p for p in perspectives if p.success]
        committee_votes = {
            p.perspective: {
                "vote": ("BUY" if p.conviction_score >= 6 else "HOLD"
                         if p.conviction_score >= 4 else "PASS"),
                "conviction": p.conviction_score,
                "rationale": (p.analysis.get("thesis", "")
                              if p.success else "failed"),
            }
            for p in perspectives
        }
        return {
            "thesis": validated.get("thesis", f"Synthesized from "
                                     f"{len(success)} perspectives"),
            "evidence": validated.get("evidence",
                                      {"sources": evidence.missing_sources}),
            "bull_case": validated.get("bull_case",
                                       {"narrative": ""}),
            "bear_case": validated.get("bear_case",
                                       {"narrative": ""}),
            "risks": validated.get("risks", []),
            "valuation": validated.get("valuation",
                                       {"method": "multi-perspective"}),
            "portfolio_impact": validated.get("portfolio_impact", {}),
            "guardian_impact": validated.get("guardian_impact",
                                             {"compliant": True}),
            "committee": {
                "consensus": self._consensus(success),
                "disagreements": self._disagreements(success),
                "perspectives": committee_votes,
            },
            "decision_context": validated.get("decision_context", {}),
            "invalidation_conditions": validated.get(
                "invalidation_conditions", [],
            ),
        }

    @staticmethod
    def _consensus(successful: list[PerspectiveResult]) -> str:
        buys = sum(1 for p in successful
                   if p.conviction_score >= 6)
        if buys >= 4:
            return "BUY"
        if buys >= 2:
            return "HOLD"
        return "PASS"

    @staticmethod
    def _disagreements(successful: list[PerspectiveResult]) -> list[dict]:
        scores = [p.conviction_score for p in successful
                  if p.conviction_score is not None]
        if not scores:
            return []
        avg = sum(scores) / len(scores)
        return [
            {"perspective": p.perspective,
             "conviction": p.conviction_score,
             "deviation": p.conviction_score - avg}
            for p in successful
            if abs(p.conviction_score - avg) > 1.5
        ]


# ═══════════════════════════════════════════════════════════════════════════
# ConfidenceEngine — deterministic, not LLM-generated
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ConfidenceOutput:
    score: int
    level: str
    recommendation: str
    model_version: int
    breakdown: dict[str, int]


class ConfidenceEngine:
    """Deterministic confidence scoring. System code owns the calculation.
    LLM never generates confidence values."""

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
                  evidence: EvidenceBundle) -> ConfidenceOutput:
        success = [p for p in perspectives if p.success]
        s_count = len(success)

        evidence_score = min(25, 5 * s_count)
        if evidence.missing_sources:
            # Missing data reduces evidence quality
            reduction = min(25, 5 * len(evidence.missing_sources))
            evidence_score = max(0, evidence_score - reduction)

        thesis_score = min(20, s_count * 3) if s_count > 0 else 0
        risk_score = 15 if s_count >= 3 else (10 if s_count >= 1 else 5)
        policy_score = 15 if s_count >= 4 else 10
        freshness_score = 10 if evidence.market_data else 5
        history_score = 5 if evidence.knowledge_memory else 0

        total = sum([evidence_score, thesis_score, risk_score,
                     policy_score, freshness_score, history_score])

        level = "HIGH" if total >= 80 else ("MEDIUM" if total >= 50
                                            else "LOW")
        recommendation = ("BUY" if total >= 65 else
                          ("HOLD" if total >= 35 else "PASS"))

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


# ═══════════════════════════════════════════════════════════════════════
# ResearchIntelligencePipeline — integration layer
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ResearchOutput:
    run_id: UUID
    status: str
    perspectives: list[PerspectiveResult]
    memo: Optional[dict] = None
    confidence: Optional[ConfidenceOutput] = None
    error: Optional[str] = None


class ResearchIntelligencePipeline:
    """End-to-end research intelligence loop.

    EvidenceCollector → PerspectiveExecutor → MemoGenerator →
    ConfidenceEngine → InvestmentMemo.
    """

    def __init__(
        self,
        evidence_collector: object,
        perspective_executor: object,
        memo_generator: MemoGenerator,
        confidence_engine: ConfidenceEngine,
    ):
        self.evidence = evidence_collector
        self.executor = perspective_executor
        self.memo = memo_generator
        self.confidence = confidence_engine

    def execute(self, session: Session, run_id: UUID,
                household_id: UUID,
                symbol: Optional[str] = None,
                ) -> ResearchOutput:
        # Phase 1: Evidence
        bundle = self.evidence.collect(session, household_id, symbol)

        # Phase 2: Perspectives
        perspectives = self._execute_perspectives(
            session, run_id, bundle,
        )
        session.commit()

        # Phase 3: Memo (gate: all 6 must succeed)
        memo = self.memo.generate(session, run_id, perspectives, bundle)

        # Phase 4: Confidence
        conf = self.confidence.calculate(perspectives, bundle)

        # Phase 5: Store
        self._store_memo(session, run_id, memo, conf)
        session.commit()

        return ResearchOutput(
            run_id=run_id,
            status="completed" if memo else "completed",
            perspectives=perspectives,
            memo=memo,
            confidence=conf,
        )

    def _execute_perspectives(
        self, session: Session, run_id: UUID, bundle: EvidenceBundle,
    ) -> list[PerspectiveResult]:
        PERSPECTIVES = [
            ("value", "claude-sonnet-4"),
            ("growth", "gpt-4o"),
            ("risk", "claude-sonnet-4"),
            ("macro", "gpt-4o"),
            ("policy", "claude-sonnet-4"),
            ("portfolio_fit", "gpt-4o"),
        ]
        results = []
        for perspective, model in PERSPECTIVES:
            try:
                result = self._execute_one_perspective(
                    session, run_id, perspective, model, bundle,
                )
                results.append(result)
            except Exception as exc:
                results.append(PerspectiveResult(
                    perspective=perspective, model=model,
                    provider="unknown", analysis={},
                    conviction_score=0, success=False,
                    error=str(exc)[:500],
                ))
        return results

    def _execute_one_perspective(
        self, session, run_id, perspective, model, bundle,
    ) -> PerspectiveResult:
        """Execute a single perspective and store result."""
        # Build prompt from evidence
        sys_prompt = (
            f"You are the {perspective} analyst for CompoundOS, "
            "an AI-assisted family office investment research system. "
            "Analyze the evidence and return structured JSON with: "
            "perspective, thesis, conviction_score (1-10), key_metrics."
        )
        user_prompt = self._build_perspective_prompt(
            perspective, bundle,
        )

        # Execute governed LLM call, requesting the configured model
        result = self.executor.execute(
            session, run_id, perspective, sys_prompt, user_prompt,
            requested_model=model,
        )

        # Store perspective_analyses with real provenance
        self._store_analysis(session, run_id, perspective, result)

        return PerspectiveResult(
            perspective=perspective,
            model=result.actual_model,
            provider=result.actual_provider,
            analysis=result.validated,
            conviction_score=result.validated.get("conviction_score", 5),
            success=True,
        )

    def _build_perspective_prompt(self, perspective: str,
                                  bundle: EvidenceBundle) -> str:
        parts = [f"Analyze from a {perspective} perspective.",
                 ""]
        if bundle.market_data:
            parts.append("Market Data: " + json.dumps(bundle.market_data))
        if bundle.portfolio_context:
            parts.append("Portfolio: " + json.dumps(
                bundle.portfolio_context))
        if bundle.guardian_status:
            parts.append("Guardian: " + json.dumps(
                bundle.guardian_status))
        if bundle.knowledge_memory:
            parts.append("Knowledge: " + json.dumps(
                bundle.knowledge_memory))
        if bundle.missing_sources:
            parts.append("Missing: " + ", ".join(bundle.missing_sources))
        return "\n".join(parts)

    def _store_analysis(self, session: Session, run_id: UUID,
                        perspective: str,
                        result: ExecutionResult) -> None:
        # Record the REAL execution result, never the requested model. The
        # legacy `model` column stores the actual (served) model for backward
        # compatibility; requested/resolved/provider/actual_model are stored
        # explicitly for provenance (Learning Loop / model evaluation).
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "INSERT INTO perspective_analyses"
                " (id, run_id, perspective, model, prompt_version,"
                " requested_model, resolved_model, provider, actual_model,"
                " analysis, conviction_score, started_at, completed_at)"
                " VALUES (:id, :rid, :p, :m, 1,"
                " :rm, :rvm, :prov, :am,"
                " CAST(:a AS jsonb), :cs, :now, :now)"
            ),
            {
                "id": uuid4(), "rid": run_id, "p": perspective,
                "m": result.actual_model,
                "rm": result.requested_model,
                "rvm": result.resolved_model,
                "prov": result.actual_provider,
                "am": result.actual_model,
                "a": json.dumps(result.validated),
                "cs": result.validated.get("conviction_score", 5),
                "now": now,
            },
        )

    def _store_memo(self, session: Session, run_id: UUID,
                    memo: Optional[dict],
                    conf: Optional[ConfidenceOutput]) -> None:
        if not memo or not conf:
            return
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "INSERT INTO investment_memos"
                " (id, run_id, memo, synthesis_model,"
                " confidence_score, confidence_level,"
                " recommendation, generated_at)"
                " VALUES (:id, :rid, CAST(:memo AS jsonb), 'synthesis',"
                " :score, :level, :rec, :now)"
            ),
            {
                "id": uuid4(), "rid": run_id,
                "memo": json.dumps(memo),
                "score": conf.score, "level": conf.level,
                "rec": conf.recommendation, "now": now,
            },
        )
