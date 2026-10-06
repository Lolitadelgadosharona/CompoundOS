# Quote identity validation

VERIFIED FACT: Yahoo identification and price parsing validate the actual returned symbol, exchange, instrument type and currency against the requested instrument. FX parsing validates the actual provider pair and returned quote currency. Service refresh repeats identity checks before persisting observations. Observation identity is append-only evidence.

Mismatch produces `INSTRUMENT_IDENTITY_MISMATCH` / `QUOTE_IDENTITY_MISMATCH` as appropriate. Unsupported/unresolved instruments fail closed. Price/FX amounts must be positive and finite, timestamps must not be future or beyond the common freshness limit, and qualities must be OBSERVED/DELAYED. GBp remains a price unit with multiplier .01 and canonical GBP currency.

Latest future observations cannot silently fall back to an older trusted observation. Valuation rejects observed quotes with unresolved identity or an unconfigured source; they cannot contribute a trusted total. Old observations without identity are not backfilled by guessing.

Real Yahoo technical probe: AAPL, MSFT, NVDA, TSM, BRK.B, QQQ, VTI, VXUS, SGOV returned matching identities. Ambiguous names require selection, invalid ticker fails, and unsupported/ambiguous results do not automatically resolve. Weekend observations can be stale and therefore remain blocked for recommendations despite correct identity.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
