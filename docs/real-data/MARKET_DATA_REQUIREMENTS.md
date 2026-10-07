# Production market data contract

BrokerProvider (inventory), MarketDataProvider (identity/quotes/history), FXProvider (exchange rates) remain separate. Existing launch_providers and valuation gates are retained; no live provider was configured.

Required identity: canonical UUID, stable provider ID, name, exchange/MIC, currency, instrument type, class-share mapping, ISIN where available, provider crosswalk/version. Search must return explicit ambiguous candidates, not guess. Minimum universe capability US stocks and ETFs; no supported-symbol whitelist.

Quote: finite positive Decimal, native quote currency/unit_multiplier (GBp→GBP0.01 explicit), exchange/session, source, provider_ref, observed as_of, retrieved_at, LIVE/DELAYED/STALE/UNKNOWN, delay and age. Future timestamp rejects; missing currency/source/identity rejects. Approved historical adjusted close plus raw close, adjustment method/version, split/dividend events, timezone/trading calendar, delisted instruments and correction provenance. Never infer real prices from cost basis.

Future ETF class/geography/sector/look-through and benchmarks require actual sourced metadata. Unknown exposure remains NOT EVALUATED. Existing data age/Policy/Guardian thresholds are unchanged. Provider quote does not establish permission for internal analytics, derived evidence or LLM use. Recommendation requires all inventory, price, FX, Policy and Committee gates; no unknown omitted asset/zero/1 conversion.
