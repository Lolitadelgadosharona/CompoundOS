"""Investment case validation — Sprint 015 Slice A.

Validation framework for evaluating AI-generated memos against
quality criteria. Owner reviews all memos — no AI filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationScore:
    dimension: str
    score: int  # 1-10
    notes: str = ""


@dataclass
class ValidationReport:
    symbol: str
    memo_id: str
    scores: list[ValidationScore] = field(default_factory=list)
    overall: int = 0
    recommendation: str = ""

    @property
    def passed(self) -> bool:
        return self.overall >= 5

    @property
    def dimensions(self) -> list[str]:
        return [s.dimension for s in self.scores]


VALIDATION_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "BRK.B", "JNJ"]

EVALUATION_DIMENSIONS = [
    "thesis_clarity",
    "evidence_quality",
    "risk_analysis",
    "actionability",
    "confidence_calibration",
]


class ValidationService:
    """Evaluates AI-generated memos against quality criteria.

    All memos pass through — this is a quality measurement tool,
    not a gate. The Owner makes the final decision.
    """

    @staticmethod
    def evaluate(
        symbol: str, memo_id: str,
        scores: Optional[list[tuple[str, int, str]]] = None,
    ) -> ValidationReport:
        """Create a validation report for a memo."""
        if scores is None:
            scores = []
        vscores = [ValidationScore(d, s, n) for d, s, n in scores]
        overall = (sum(s.score for s in vscores) // max(len(vscores), 1)
                   if vscores else 5)
        return ValidationReport(
            symbol=symbol,
            memo_id=memo_id,
            scores=vscores,
            overall=overall,
            recommendation=(
                "Actionable" if overall >= 7
                else "Needs review" if overall >= 5
                else "Insufficient"
            ),
        )

    @staticmethod
    def batch_evaluate(
        symbols: Optional[list[str]] = None,
    ) -> list[ValidationReport]:
        """Evaluate multiple symbols. Placeholder for real runs."""
        syms = symbols or VALIDATION_SYMBOLS
        reports = []
        for sym in syms:
            report = ValidationReport(
                symbol=sym, memo_id="pending", overall=0,
                recommendation="Not yet evaluated",
            )
            reports.append(report)
        return reports

    @staticmethod
    def summary(reports: list[ValidationReport]) -> dict:
        """Aggregate validation results across symbols."""
        if not reports:
            return {"total": 0, "passed": 0, "failed": 0}
        passed = sum(1 for r in reports if r.passed)
        return {
            "total": len(reports),
            "passed": passed,
            "failed": len(reports) - passed,
            "avg_score": sum(r.overall for r in reports) // len(reports),
        }
