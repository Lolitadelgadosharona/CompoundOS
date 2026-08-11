"""Tests for Sprint 014 Slice D — Portfolio Intelligence."""

from apps.api.services.portfolio_intelligence import (
    Holding,
    PortfolioIntelligenceService,
)


class TestEmptyPortfolio:
    def test_empty_returns_zero_context(self):
        ctx = PortfolioIntelligenceService.analyze([])
        assert ctx.total_value == 0
        assert ctx.holding_count == 0

    def test_empty_position_weight_zero(self):
        ctx = PortfolioIntelligenceService.analyze([])
        assert ctx.position_weight("AAPL") == 0


class TestAllocation:
    def test_single_holding_100_pct(self):
        holdings = [Holding("AAPL", 100, 150, 175, "tech")]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        assert ctx.total_value == 17500.0
        assert len(ctx.allocation) == 1
        assert ctx.allocation[0].label == "tech"
        assert abs(ctx.allocation[0].value_pct - 100) < 0.1

    def test_multi_sector_allocation(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech"),
            Holding("JNJ", 100, 150, 160, "healthcare"),
            Holding("TLT", 100, 100, 95, "bonds"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        assert len(ctx.allocation) == 3

    def test_allocation_sums_to_100(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech"),
            Holding("GOOGL", 50, 140, 180, "tech"),
            Holding("JNJ", 100, 150, 160, "healthcare"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        total_pct = sum(a.value_pct for a in ctx.allocation)
        assert abs(total_pct - 100) < 0.1


class TestConcentration:
    def test_single_holding_over_20pct_warns(self):
        holdings = [Holding("AAPL", 1000, 150, 175, "tech")]
        ctx = PortfolioIntelligenceService.analyze(holdings, "AAPL")
        assert len(ctx.concentration_warnings) > 0

    def test_small_position_no_warning(self):
        holdings = [
            Holding("AAPL", 40, 150, 175, "tech"),
            Holding("GOOGL", 40, 140, 180, "tech"),
            Holding("JNJ", 50, 150, 160, "healthcare"),
            Holding("PG", 60, 140, 155, "consumer"),
            Holding("XOM", 60, 60, 115, "energy"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        assert len(ctx.concentration_warnings) == 0

    def test_sector_over_40pct_warns(self):
        holdings = [
            Holding("AAPL", 1000, 150, 175, "tech"),
            Holding("JNJ", 100, 150, 160, "healthcare"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        has_sector_warning = any(
            "sector" in w.lower() for w in ctx.concentration_warnings
        )
        assert has_sector_warning


class TestImpactIfAdded:
    def test_impact_same_symbol(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech"),
            Holding("MSFT", 100, 300, 350, "tech"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        impact = PortfolioIntelligenceService.impact_if_added(
            ctx, "AAPL", 5000,
        )
        assert impact["new_weight_pct"] > impact["current_weight_pct"]

    def test_impact_new_symbol(self):
        holdings = [Holding("AAPL", 100, 150, 175, "tech")]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        impact = PortfolioIntelligenceService.impact_if_added(
            ctx, "MSFT", 5000,
        )
        assert impact["current_weight_pct"] == 0
        assert impact["new_weight_pct"] > 0


class TestCurrencyExposure:
    def test_single_currency(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech", "USD"),
            Holding("GOOGL", 50, 140, 180, "tech", "USD"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        assert ctx.currency_exposure.get("USD", 0) > 99

    def test_multi_currency(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech", "USD"),
            Holding("NVO", 100, 100, 120, "healthcare", "DKK"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        assert len(ctx.currency_exposure) == 2


class TestPositionWeight:
    def test_weight_calculation(self):
        holdings = [
            Holding("AAPL", 100, 150, 175, "tech"),
            Holding("GOOGL", 100, 140, 180, "tech"),
        ]
        ctx = PortfolioIntelligenceService.analyze(holdings)
        aapl_w = ctx.position_weight("AAPL")
        googl_w = ctx.position_weight("GOOGL")
        assert abs(aapl_w + googl_w - 100) < 0.1


class TestNoTrading:
    def test_service_has_no_trade_methods(self):
        """PortfolioIntelligenceService must not contain trade/order/execute."""
        methods = [m for m in dir(PortfolioIntelligenceService)
                   if not m.startswith("_")]
        assert "trade" not in methods
        assert "execute" not in methods
        assert "order" not in methods
        assert "broker" not in methods
