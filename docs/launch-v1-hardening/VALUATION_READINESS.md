# Valuation readiness

VERIFIED FACT: The common contract retains base currency, as_of, native currencies, price/FX sources and observation times, unit multipliers, normalized values, quality reasons and trust blockers. `recommendation_ready` is true only for COMPLETE, exposed as readiness READY. INCOMPLETE/BLOCKED, COST_ESTIMATE and DEGRADED are never recommendation ready.

Trusted positions require reconciled Asset/provider identity, matching persisted observation identity, allowed quote quality, configured source, finite positive price and fresh timestamp. Required FX needs a configured source, verified actual currency pair, valid quality, finite positive rate and fresh observation. Missing required rows/inputs block completeness; nothing becomes zero or silently disappears. Direct/inverse FX and pence units share the existing Decimal valuation arithmetic. Separate position/cash queries preserve aggregation without double JOIN multiplication.

Descriptive Guardian analysis may inspect complete reported import amounts using `analysis_ready`; that flag grants no approval permission. Reported/cost/simulated amounts retain explicit quality labels. Dashboard includes trust blockers in its displayed quality reasons. Recommendation generation and approval require strict readiness; candidate evidence is re-evaluated before Committee and confirmation.

User-facing background research now checks portfolio and canonical target readiness before model execution. Research approval additionally requires a completed registry-validated report bound to the current target quote, valuation inputs and published Policy context. A Memo or Committee draft alone is insufficient.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
