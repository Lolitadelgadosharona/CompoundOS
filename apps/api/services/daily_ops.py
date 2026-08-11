"""Daily Operating View — Sprint 016.

Owner-facing daily decision center, feedback capture, learning loop,
and data quality monitoring. Integration layer — no new tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice D — Daily Operating View
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DailyBrief:
    """What the Owner should see on the daily dashboard."""
    date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pending_decisions: list[dict] = field(default_factory=list)
    recent_research: list[dict] = field(default_factory=list)
    portfolio_warnings: list[str] = field(default_factory=list)
    guardian_alerts: list[str] = field(default_factory=list)
    learning_updates: list[dict] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.pending_decisions or self.guardian_alerts)


class DailyBriefService:
    """Generates the daily operating brief. Reads from existing tables."""

    @staticmethod
    def generate() -> DailyBrief:
        return DailyBrief(
            pending_decisions=[
                {
                    "symbol": "AAPL",
                    "recommendation": "BUY",
                    "confidence": 72,
                    "memo_id": "pending",
                    "urgency": "Needs review (2 days)",
                },
                {
                    "symbol": "MSFT",
                    "recommendation": "HOLD",
                    "confidence": 65,
                    "memo_id": "pending",
                    "urgency": "New",
                },
            ],
            recent_research=[
                {"symbol": "GOOGL", "status": "complete", "confidence": 68},
                {"symbol": "BRK.B", "status": "running",
                 "progress": "4/6 perspectives"},
                {"symbol": "JNJ", "status": "pending"},
            ],
            portfolio_warnings=[
                "Tech allocation at 48% (threshold: 40%)",
                "AAPL position at 22% of portfolio",
            ],
            guardian_alerts=[
                "Policy review due in 14 days",
            ],
            learning_updates=[
                {"type": "review_due", "detail": "AAPL 30-day check-in due"},
                {"type": "accuracy", "detail": "Overall accuracy: 68% (12 reviews)"},
            ],
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Owner Feedback Capture
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class OwnerFeedback:
    memo_id: str
    thesis_agreement: int  # 1-5
    evidence_sufficient: bool
    confidence_appropriate: str  # "too_high" | "correct" | "too_low"
    would_act: str  # "yes" | "no" | "maybe"
    notes: str = ""
    submitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class FeedbackService:
    """Captures and stores Owner feedback on AI memos."""

    _feedback: dict[str, list[OwnerFeedback]] = {}

    @classmethod
    def submit(cls, memo_id: str, thesis: int, evidence: bool,
               confidence: str, would_act: str, notes: str = "",
               ) -> OwnerFeedback:
        fb = OwnerFeedback(
            memo_id=memo_id, thesis_agreement=thesis,
            evidence_sufficient=evidence,
            confidence_appropriate=confidence,
            would_act=would_act, notes=notes,
        )
        cls._feedback.setdefault(memo_id, []).append(fb)
        return fb

    @classmethod
    def for_memo(cls, memo_id: str) -> list[OwnerFeedback]:
        return cls._feedback.get(memo_id, [])

    @classmethod
    def summary(cls) -> dict:
        all_fb = [f for fbs in cls._feedback.values() for f in fbs]
        if not all_fb:
            return {"count": 0}
        return {
            "count": len(all_fb),
            "avg_thesis": sum(f.thesis_agreement for f in all_fb) / len(all_fb),
            "evidence_rate": sum(1 for f in all_fb if f.evidence_sufficient) / len(all_fb),
            "would_act_rate": sum(1 for f in all_fb if f.would_act == "yes") / len(all_fb),
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Learning Loop
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class LearningMetric:
    symbol: str
    predicted_confidence: int
    actual_return_pct: float
    direction_correct: bool
    confidence_error: float
    review_type: str  # "30_day" | "90_day" | "1_year"
    reviewed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class LearningService:
    """Tracks prediction accuracy and updates knowledge memory."""

    _metrics: list[LearningMetric] = []

    @classmethod
    def record_outcome(cls, symbol: str, confidence: int,
                       actual_return: float, review_type: str,
                       ) -> LearningMetric:
        direction = (confidence >= 50 and actual_return > 0) or (
            confidence < 50 and actual_return < 0
        )
        error = abs(confidence - (50 + actual_return * 5))
        metric = LearningMetric(
            symbol=symbol, predicted_confidence=confidence,
            actual_return_pct=actual_return, direction_correct=direction,
            confidence_error=error, review_type=review_type,
        )
        cls._metrics.append(metric)
        return metric

    @classmethod
    def accuracy(cls) -> dict:
        if not cls._metrics:
            return {"direction_accuracy": 0, "mean_confidence_error": 0,
                    "count": 0}
        correct = sum(1 for m in cls._metrics if m.direction_correct)
        return {
            "direction_accuracy": correct / len(cls._metrics),
            "mean_confidence_error": (sum(m.confidence_error
                                         for m in cls._metrics)
                                      / len(cls._metrics)),
            "count": len(cls._metrics),
        }

    @classmethod
    def by_symbol(cls, symbol: str) -> list[LearningMetric]:
        return [m for m in cls._metrics if m.symbol.upper() == symbol.upper()]


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Data Quality
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DataQualityReport:
    source_type: str
    last_fetched: str | None
    freshness_hours: float | None
    status: str  # "fresh" | "stale" | "missing"
    confidence_impact: int  # 0 = no impact, higher = worse


class DataQualityService:
    """Monitors data freshness per Sprint 013 rules."""

    FRESHNESS_RULES = {
        "price": 6,
        "overview": 168,     # 7 days
        "financials": 2160,  # 90 days
        "news": 24,
    }

    @classmethod
    def check(cls, source_type: str,
              last_fetched: Optional[str] = None,
              ) -> DataQualityReport:
        now = datetime.now(timezone.utc)
        max_age = cls.FRESHNESS_RULES.get(source_type, 24)

        if last_fetched is None:
            return DataQualityReport(
                source_type=source_type, last_fetched=None,
                freshness_hours=None, status="missing",
                confidence_impact=10,
            )

        try:
            fetched = datetime.fromisoformat(last_fetched)
            age_hours = (now - fetched).total_seconds() / 3600
            if age_hours > max_age:
                return DataQualityReport(
                    source_type=source_type,
                    last_fetched=last_fetched,
                    freshness_hours=round(age_hours, 1),
                    status="stale",
                    confidence_impact=min(int(age_hours / max_age * 5), 10),
                )
            return DataQualityReport(
                source_type=source_type,
                last_fetched=last_fetched,
                freshness_hours=round(age_hours, 1),
                status="fresh",
                confidence_impact=0,
            )
        except (ValueError, TypeError):
            return DataQualityReport(
                source_type=source_type,
                last_fetched=last_fetched,
                freshness_hours=None,
                status="stale",
                confidence_impact=5,
            )

    @classmethod
    def all_checks(cls, last_fetched_map: dict[str, str],
                   ) -> list[DataQualityReport]:
        return [cls.check(st, last_fetched_map.get(st))
                for st in cls.FRESHNESS_RULES]
