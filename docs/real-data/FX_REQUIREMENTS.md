# FX contract

Required USD/CNY and CNY/USD. Decimal rate means quote units per one base unit. Record pair, rate, provider/ref, as_of/retrieved_at, LIVE/DELAYED/STALE/UNKNOWN, freshness and inversion provenance. Inversion only of finite positive verified opposite rate; store source pair and derived reciprocal. Validate pair direction, source timestamps and units; never assume rate1 except identical currency with explicit identity conversion.

CNY amount / (CNY per USD) = USD; USD amount × (CNY per USD) = CNY. Preserve original cash/flow ledger. Aggregation only after common base/as_of using existing valuation; no mixing amounts and no broker FX authorization assumption. CNH differs from CNY and is not substituted. Calendar/session-aware freshness requires future approved contract; no threshold relaxation this sprint. Test inverse/missing/stale/future/nonfinite cases remains covered by existing full valuation regressions. No live FX requests or subscriptions here.
