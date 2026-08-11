"""Real Operation & Calibration — Sprint 021.

Decision accuracy, knowledge compounding, portfolio validation,
and workflow automation. No trading. Advisory only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice B — Decision Accuracy Expansion
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AccuracyMetric:
    metric: str
    value: float
    detail: str = ""
    rating: str = ""

    def __post_init__(self):
        if "direction" in self.metric.lower():
            if self.value >= 0.75:
                self.rating = "excellent"
            elif self.value >= 0.60:
                self.rating = "good"
            elif self.value >= 0.50:
                self.rating = "adequate"
            else:
                self.rating = "poor"


@dataclass
class PerspectiveAccuracy:
    perspective: str
    correct: int
    total: int
    accuracy: float = 0.0

    def __post_init__(self):
        self.accuracy = self.correct / max(self.total, 1)


@dataclass
class DecisionOutcome:
    symbol: str
    decision: str
    confidence: int
    decision_date: str
    decision_price: float
    current_price: float
    days_elapsed: int
    return_pct: float = 0.0
    direction_correct: bool = False
    review_type: str = ""

    def __post_init__(self):
        self.return_pct = round(
            (self.current_price - self.decision_price)
            / self.decision_price * 100, 2,
        )
        self.direction_correct = (
            (self.confidence >= 50 and self.return_pct > 0)
            or (self.confidence < 50 and self.return_pct < 0)
        )


class AccuracyService:
    """Tracks decisions vs. outcomes. No trading."""

    @staticmethod
    def record_outcomes(
        decisions: list[dict], current_prices: dict[str, float],
    ) -> list[DecisionOutcome]:
        outcomes = []
        for d in decisions:
            price = current_prices.get(d["symbol"], d["decision_price"])
            outcome = DecisionOutcome(
                symbol=d["symbol"], decision=d["decision"],
                confidence=d["confidence"],
                decision_date=d["date"],
                decision_price=d["decision_price"],
                current_price=price,
                days_elapsed=d.get("days_elapsed", 0),
                review_type=d.get("review_type", "30_day"),
            )
            outcomes.append(outcome)
        return outcomes

    @staticmethod
    def calculate_metrics(
        outcomes: list[DecisionOutcome],
    ) -> list[AccuracyMetric]:
        if not outcomes:
            return [AccuracyMetric(metric="direction_accuracy",
                                   value=0, detail="No outcomes yet")]
        correct = sum(1 for o in outcomes if o.direction_correct)
        return [
            AccuracyMetric(
                metric="direction_accuracy",
                value=round(correct / len(outcomes), 3),
                detail=f"{correct}/{len(outcomes)} correct",
            ),
            AccuracyMetric(
                metric="average_return",
                value=round(
                    sum(o.return_pct for o in outcomes) / len(outcomes), 2,
                ),
                detail=f"{len(outcomes)} decisions tracked",
            ),
            AccuracyMetric(
                metric="confidence_calibration",
                value=round(
                    1.0 - abs(sum(
                        o.confidence / 100 - abs(o.return_pct) / 30
                        for o in outcomes
                    )) / max(len(outcomes), 1), 3,
                ),
                detail="Higher = better calibrated",
            ),
        ]

    @staticmethod
    def by_perspective(
        perspective_data: list[dict],
    ) -> list[PerspectiveAccuracy]:
        return [
            PerspectiveAccuracy(
                perspective=p["perspective"],
                correct=p["correct"], total=p["total"],
            )
            for p in perspective_data
        ]


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Knowledge Compounding
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CrossReference:
    current_thesis: str
    past_thesis: str = ""
    past_date: str = ""
    past_confidence: int = 0
    contradiction: bool = False
    contradiction_detail: str = ""
    past_outcome: Optional[dict] = None


class KnowledgeService:
    """Cross-reference current research with past memos."""

    @staticmethod
    def cross_reference(
        symbol: str, current_thesis: str,
        past_memos: list[dict],
    ) -> CrossReference:
        if not past_memos:
            return CrossReference(current_thesis=current_thesis)
        latest = past_memos[-1]
        ref = CrossReference(
            current_thesis=current_thesis,
            past_thesis=latest.get("thesis", ""),
            past_date=latest.get("date", ""),
            past_confidence=latest.get("confidence", 0),
            past_outcome=latest.get("outcome"),
        )
        # Simple contradiction: BUY→HOLD or confidence swing >30
        past_rec = latest.get("recommendation", "")
        curr_keywords = current_thesis.lower()
        if "sell" in curr_keywords and past_rec == "BUY":
            ref.contradiction = True
            ref.contradiction_detail = (
                f"Shifted from {past_rec} to SELL — significant change"
            )
        if abs(latest.get("confidence", 0) - 50) > 30:
            ref.contradiction = True
            ref.contradiction_detail = (
                "Confidence swing >30 points vs. prior analysis"
            )
        return ref

    @staticmethod
    def context_blurb(ref: CrossReference) -> str:
        if not ref.past_thesis:
            return "No prior analysis available for this symbol."
        blurb = (
            f"Prior analysis ({ref.past_date}): "
            f"Confidence {ref.past_confidence}. "
        )
        if ref.past_outcome:
            ok = "correct" if ref.past_outcome.get("correct") else "incorrect"
            blurb += f"Outcome: direction {ok}. "
        if ref.contradiction:
            blurb += f"ALERT: {ref.contradiction_detail}"
        return blurb


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Real Portfolio Validation
# ═══════════════════════════════════════════════════════════════════════

REQUIRED_CSV_FIELDS = ["symbol", "shares", "cost_basis", "asset_type"]
OPTIONAL_CSV_FIELDS = ["account", "purchase_date", "currency", "notes"]


@dataclass
class ImportResult:
    rows_imported: int
    rows_skipped: int
    errors: list[str]
    total_value: float = 0.0
    currency_flags: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class PortfolioValidationService:
    """CSV import and calculation verification."""

    @staticmethod
    def validate_csv(
        rows: list[dict], expected_total: Optional[float] = None,
    ) -> ImportResult:
        imported = 0
        skipped = 0
        errors: list[str] = []
        total = 0.0
        currency_flags: list[str] = []

        for i, row in enumerate(rows, 1):
            missing = [f for f in REQUIRED_CSV_FIELDS if f not in row]
            if missing:
                skipped += 1
                errors.append(f"Row {i}: missing {missing}")
                continue
            try:
                shares = float(row["shares"])
                cost = float(row["cost_basis"])
                price = cost  # use cost as proxy if no current price
                total += shares * price
                imported += 1
                if row.get("currency", "USD") != "USD":
                    currency_flags.append(
                        f"{row['symbol']} ({row.get('currency', '?')})"
                        " — check currency",
                    )
            except (ValueError, TypeError):
                skipped += 1
                errors.append(f"Row {i}: invalid numeric value")

        result = ImportResult(
            rows_imported=imported, rows_skipped=skipped,
            errors=errors, total_value=total,
            currency_flags=currency_flags,
        )

        if expected_total is not None and total > 0:
            pct_diff = abs(total - expected_total) / expected_total * 100
            if pct_diff > 1:
                result.errors.append(
                    f"Total ${total:,.2f} differs from expected "
                    f"${expected_total:,.2f} by {pct_diff:.1f}%"
                    f" (>1% tolerance)",
                )

        return result


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Workflow Automation
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ScheduledTask:
    task_id: str
    description: str
    frequency: str  # monthly | quarterly | reminder
    next_due: str
    action: str  # snapshot | research_reminder | report
    auto_execute: bool = False


class WorkflowAutomationService:
    """Reminders and snapshots. Never auto-executes trades."""

    @staticmethod
    def reminders() -> list[ScheduledTask]:
        now = datetime.now(timezone.utc)
        return [
            ScheduledTask(
                task_id="snapshot-monthly",
                description="Monthly portfolio snapshot",
                frequency="monthly",
                next_due=now.replace(day=1).isoformat(),
                action="snapshot",
                auto_execute=True,
            ),
            ScheduledTask(
                task_id="research-reminder",
                description="Research stale: AAPL (last: 92 days ago)",
                frequency="reminder",
                next_due=now.isoformat(),
                action="research_reminder",
            ),
            ScheduledTask(
                task_id="report-quarterly",
                description="Q4 2026 quarterly report due",
                frequency="quarterly",
                next_due=now.replace(month=12).isoformat(),
                action="report",
            ),
        ]
