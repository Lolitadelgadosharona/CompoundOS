"""Intelligence Expansion — Sprint 017.

Research quality scoring, memory evolution, macro intelligence,
and multi-asset support. Integration layer — no new tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice D — Research Quality Scoring
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QualityScore:
    completeness: int      # 1-10 — all 11 sections populated?
    evidence_quality: int   # 1-10 — sources cited, freshness?
    balance: int            # 1-10 — bear case proportional?
    confidence_alignment: int  # 1-10 — conviction matches depth?
    clarity: int            # 1-10 — thesis well-structured?
    overall: int = 0
    label: str = ""

    def __post_init__(self):
        self.overall = round(
            self.completeness * 0.25 + self.evidence_quality * 0.25
            + self.balance * 0.20 + self.confidence_alignment * 0.15
            + self.clarity * 0.15,
        )
        if self.overall >= 8:
            self.label = "Strong Analysis"
        elif self.overall >= 5:
            self.label = "Adequate"
        else:
            self.label = "Needs Improvement"


class QualityScorer:
    """Automated memo quality scoring. Informational only — no gating."""

    REQUIRED_SECTIONS = [
        "thesis", "evidence", "bull_case", "bear_case", "risks",
        "valuation", "portfolio_impact", "guardian_impact",
        "committee", "decision_context", "invalidation_conditions",
    ]

    @classmethod
    def score(cls, memo: dict, source_count: int = 0,
              data_age_hours: float = 0) -> QualityScore:
        # Completeness: how many of 11 sections are present + non-empty
        filled = sum(1 for s in cls.REQUIRED_SECTIONS
                     if memo.get(s, ""))
        completeness = min(10, filled)

        # Evidence quality: sources + freshness
        if source_count >= 3 and data_age_hours < 24:
            eq_score = 10
        elif source_count >= 1:
            eq_score = 7
        elif "evidence" in memo and memo["evidence"]:
            eq_score = 5
        else:
            eq_score = 2
        evidence_quality = max(2, eq_score - min(
            int(data_age_hours / 48), 3,
        ))

        # Balance: bear case length vs bull case
        bull_len = len(str(memo.get("bull_case", "")))
        bear_len = len(str(memo.get("bear_case", "")))
        ratio = bear_len / max(bull_len, 1)
        if ratio >= 0.8:
            balance = 10
        elif ratio >= 0.5:
            balance = 7
        elif ratio >= 0.3:
            balance = 5
        else:
            balance = 3

        # Confidence alignment: does memo have conviction_score vs
        # evidence depth?
        conf = memo.get("confidence_score", 0)
        if conf >= 80 and source_count >= 3:
            ca = 10
        elif conf >= 60 and source_count >= 2:
            ca = 8
        elif conf >= 40:
            ca = 6
        else:
            ca = 4
        confidence_alignment = ca

        # Clarity: thesis length (heuristic)
        thesis_len = len(str(memo.get("thesis", "")))
        if thesis_len > 100:
            clarity = 8
        elif thesis_len > 30:
            clarity = 6
        else:
            clarity = 3

        return QualityScore(
            completeness=completeness, evidence_quality=evidence_quality,
            balance=balance, confidence_alignment=confidence_alignment,
            clarity=clarity,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Research Memory Evolution
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MemoryEntry:
    symbol: str
    memo_id: str
    thesis: str
    confidence: int
    recommendation: str
    created_at: str
    outcome: Optional[dict] = None
    tags: list[str] = field(default_factory=list)


class ResearchMemory:
    """Per-entity indexed memory. Immutable snapshots, append-only."""

    _entries: dict[str, list[MemoryEntry]] = {}

    @classmethod
    def store(cls, entry: MemoryEntry) -> None:
        cls._entries.setdefault(entry.symbol.upper(), []).append(entry)

    @classmethod
    def for_symbol(cls, symbol: str) -> list[MemoryEntry]:
        return cls._entries.get(symbol.upper(), [])

    @classmethod
    def latest(cls, symbol: str) -> Optional[MemoryEntry]:
        entries = cls.for_symbol(symbol)
        return entries[-1] if entries else None

    @classmethod
    def with_outcome(cls, symbol: str, memo_id: str,
                     outcome: dict) -> None:
        for e in cls.for_symbol(symbol):
            if e.memo_id == memo_id:
                e.outcome = outcome
                return

    @classmethod
    def summary(cls, symbol: str) -> dict:
        entries = cls.for_symbol(symbol)
        if not entries:
            return {"count": 0}
        with_outcomes = [e for e in entries if e.outcome]
        return {
            "count": len(entries),
            "latest_thesis": entries[-1].thesis[:100] if entries else "",
            "outcomes": len(with_outcomes),
            "avg_confidence": (sum(e.confidence for e in entries)
                               // max(len(entries), 1)),
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Macro Intelligence
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MacroSnapshot:
    fed_funds_rate: float = 0.0
    ten_year_yield: float = 0.0
    two_ten_spread: float = 0.0
    sp500_ytd: float = 0.0
    vix: float = 0.0
    sector_performance: dict[str, float] = field(default_factory=dict)
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    @property
    def recession_signal(self) -> bool:
        return self.two_ten_spread < 0

    @property
    def market_regime(self) -> str:
        if self.vix > 30:
            return "high_volatility"
        if self.sp500_ytd < -10:
            return "bear"
        if self.sp500_ytd > 10:
            return "bull"
        return "neutral"

    def context_blurb(self) -> str:
        """Generate a facts-only context paragraph (no prediction)."""
        parts = [
            f"Fed Funds Rate: {self.fed_funds_rate}%",
            f"10Y Yield: {self.ten_year_yield}%",
            f"2Y/10Y Spread: {self.two_ten_spread}%"
            f"{' (inverted — recession signal)' if self.recession_signal else ''}",
            f"S&P 500 YTD: {self.sp500_ytd:+.1f}%",
            f"VIX: {self.vix}",
            f"Market Regime: {self.market_regime}",
        ]
        if self.sector_performance:
            top = sorted(self.sector_performance.items(),
                         key=lambda x: -x[1])[:3]
            parts.append(
                "Top sectors: "
                + ", ".join(f"{s}: {v:+.1f}%" for s, v in top),
            )
        return " | ".join(parts) + "."


class MacroService:
    """Macro context provider. Facts only — no prediction.

    In production, fetches from FRED, Yahoo Finance, or cached DB.
    For Sprint 017, returns a representative snapshot.
    """

    @classmethod
    def snapshot(cls) -> MacroSnapshot:
        return MacroSnapshot(
            fed_funds_rate=5.25,
            ten_year_yield=4.20,
            two_ten_spread=-0.35,
            sp500_ytd=12.5,
            vix=18.2,
            sector_performance={
                "Technology": 18.5, "Healthcare": 8.2,
                "Financials": 12.1, "Energy": 5.3,
                "Consumer": 6.8, "Industrials": 9.4,
            },
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Multi-Asset Intelligence
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AssetHolding:
    symbol: str
    asset_type: str  # "stock" | "etf" | "bond" | "cash"
    shares: float
    price: float
    name: str = ""
    expense_ratio: float = 0.0  # ETFs only
    top_holdings: list[dict] = field(default_factory=list)  # ETFs only
    yield_pct: float = 0.0  # Bonds only

    @property
    def market_value(self) -> float:
        return self.shares * self.price


class MultiAssetService:
    """Multi-asset analysis. ETFs first, bonds/cash later."""

    SUPPORTED = {"stock", "etf"}

    @classmethod
    def classify(cls, holdings: list[AssetHolding]) -> dict:
        result: dict[str, dict] = {}
        for h in holdings:
            if h.asset_type not in cls.SUPPORTED:
                continue
            cat = result.setdefault(h.asset_type, {
                "count": 0, "value": 0.0, "pct": 0.0,
                "holdings": [],
            })
            cat["count"] += 1
            cat["value"] += h.market_value
            cat["holdings"].append(h.symbol)
        total = sum(c["value"] for c in result.values())
        for c in result.values():
            c["pct"] = round(c["value"] / max(total, 1) * 100, 1)
        result["total_value"] = total
        return result

    @classmethod
    def etf_detail(cls, symbol: str, top_holdings: list[dict],
                   expense_ratio: float) -> dict:
        return {
            "symbol": symbol,
            "type": "etf",
            "expense_ratio": expense_ratio,
            "top_holdings": top_holdings[:10],
            "concentration": (
                "concentrated"
                if sum(h.get("weight", 0) for h in top_holdings[:3]) > 40
                else "diversified"
            ),
        }
