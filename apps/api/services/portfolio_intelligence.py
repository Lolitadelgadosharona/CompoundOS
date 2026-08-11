"""Portfolio Intelligence Service — Sprint 014 Slice D.

Provides portfolio context for investment decisions:
holdings, allocation, concentration, currency exposure.
Deterministic calculations only — no LLM, no trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Holding:
    symbol: str
    shares: float
    cost_basis: float
    current_price: float = 0.0
    sector: str = "unknown"
    currency: str = "USD"

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def gain_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return ((self.current_price - self.cost_basis)
                / self.cost_basis * 100)


@dataclass
class AllocationSlice:
    label: str
    value_pct: float
    holdings: list[str] = field(default_factory=list)


@dataclass
class PortfolioContext:
    total_value: float = 0.0
    holdings: list[Holding] = field(default_factory=list)
    allocation: list[AllocationSlice] = field(default_factory=list)
    concentration_warnings: list[str] = field(default_factory=list)
    currency_exposure: dict[str, float] = field(default_factory=dict)

    @property
    def holding_count(self) -> int:
        return len(self.holdings)

    def position_weight(self, symbol: str) -> float:
        if self.total_value == 0:
            return 0.0
        for h in self.holdings:
            if h.symbol.upper() == symbol.upper():
                return (h.market_value / self.total_value) * 100
        return 0.0


class PortfolioIntelligenceService:
    """Deterministic portfolio calculations. No LLM. No trading."""

    CONCENTRATION_THRESHOLD_SINGLE = 20.0   # pct
    CONCENTRATION_THRESHOLD_SECTOR = 40.0   # pct

    @staticmethod
    def analyze(
        holdings: list[Holding],
        research_symbol: Optional[str] = None,
    ) -> PortfolioContext:
        """Build full portfolio context from holdings."""
        if not holdings:
            return PortfolioContext()

        total = sum(h.market_value for h in holdings)
        alloc = PortfolioIntelligenceService._calculate_allocation(
            holdings, total,
        )
        warnings = PortfolioIntelligenceService._detect_concentration(
            holdings, total, alloc,
        )
        fx = PortfolioIntelligenceService._currency_exposure(holdings, total)

        ctx = PortfolioContext(
            total_value=total,
            holdings=holdings,
            allocation=alloc,
            concentration_warnings=warnings,
            currency_exposure=fx,
        )

        # Add research-specific warnings
        if research_symbol:
            pw = ctx.position_weight(research_symbol)
            T = PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SINGLE
            if pw > T:
                w = f"{research_symbol} is {pw:.0f}% (>{T:.0f}% limit)"
                ctx.concentration_warnings.append(w)

        return ctx

    @staticmethod
    def impact_if_added(
        ctx: PortfolioContext,
        symbol: str,
        additional_value: float,
    ) -> dict:
        """Calculate portfolio impact of adding a position."""
        new_total = ctx.total_value + additional_value
        if new_total == 0:
            return {"new_weight_pct": 0, "total_after": 0}

        existing_weight = ctx.position_weight(symbol)
        new_weight = ((existing_weight / 100 * ctx.total_value
                       + additional_value) / new_total) * 100

        return {
            "symbol": symbol,
            "current_weight_pct": round(existing_weight, 2),
            "additional_value": additional_value,
            "new_total_value": round(new_total, 2),
            "new_weight_pct": round(new_weight, 2),
            "concentration_warning": (
                new_weight > PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SINGLE
            ),
            "allocation_shift": PortfolioIntelligenceService._allocation_shift(
                ctx, symbol, additional_value, new_total,
            ),
        }

    # ── internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _calculate_allocation(
        holdings: list[Holding], total: float,
    ) -> list[AllocationSlice]:
        if total == 0:
            return []
        sectors: dict[str, tuple[float, list[str]]] = {}
        for h in holdings:
            s = h.sector
            val, syms = sectors.get(s, (0.0, []))
            sectors[s] = (val + h.market_value, syms + [h.symbol])
        return [
            AllocationSlice(label=sec, value_pct=(val / total) * 100,
                            holdings=syms)
            for sec, (val, syms) in sorted(sectors.items())
        ]

    @staticmethod
    def _detect_concentration(
        holdings: list[Holding], total: float,
        alloc: list[AllocationSlice],
    ) -> list[str]:
        warnings: list[str] = []
        if total == 0:
            return warnings
        for h in holdings:
            w = (h.market_value / total) * 100
            if w > PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SINGLE:
                warnings.append(
                    f"{h.symbol} position ({w:.0f}%) exceeds "
                    f"{PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SINGLE:.0f}% threshold"
                )
        for a in alloc:
            if a.value_pct > PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SECTOR:
                warnings.append(
                    f"{a.label} sector ({a.value_pct:.0f}%) exceeds "
                    f"{PortfolioIntelligenceService.CONCENTRATION_THRESHOLD_SECTOR:.0f}% threshold"
                )
        return warnings

    @staticmethod
    def _currency_exposure(
        holdings: list[Holding], total: float,
    ) -> dict[str, float]:
        if total == 0:
            return {}
        fx: dict[str, float] = {}
        for h in holdings:
            fx[h.currency] = (fx.get(h.currency, 0.0)
                              + (h.market_value / total) * 100)
        return fx

    @staticmethod
    def _allocation_shift(
        ctx: PortfolioContext, symbol: str,
        additional_value: float, new_total: float,
    ) -> dict[str, float]:
        """How does allocation change after adding this position?"""
        target_sector = "unknown"
        for h in ctx.holdings:
            if h.symbol.upper() == symbol.upper():
                target_sector = h.sector
                break
        before = {a.label: a.value_pct for a in ctx.allocation}
        after: dict[str, float] = {}
        for sector, pct in before.items():
            if sector == target_sector:
                after[sector] = ((pct / 100 * ctx.total_value
                                  + additional_value) / new_total) * 100
            else:
                after[sector] = (pct / 100 * ctx.total_value
                                 / new_total) * 100
        if target_sector not in after:
            after[target_sector] = (additional_value / new_total) * 100
        return {s: round(after[s], 2) for s in after}
