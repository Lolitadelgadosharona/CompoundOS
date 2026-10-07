# Mapping contract

| Official field | CompoundOS destination |
|---|---|
| account id/accountId/currency | BrokerAccount.external_id/currency; owner/mode-scoped Account provider_account_id |
| positions acctId/conid | account_ref + stable external position ref; instrument provider_id=conid |
| contractDesc/localSymbol | preserved local_symbol (descriptor fallback explicitly not canonical identity) |
| secdef ticker/listingExchange/currency/name/assetClass/type | explicit canonical Instrument, existing canonical_asset |
| position | finite nonnegative Decimal quantity; short support deferred/fail closed |
| avgCost | optional reported average_cost/native currency; no quantity×cost tax-basis guess |
| ledger cashbalance/currency/timestamp | native CashBalance with observed_at and provenance |
| BASE | excluded derived cash summary; no double counting |
| mktPrice/mktValue/FX exchangerate/PnL | NOT imported into valuation/market evidence; incidental presence only |
| missing position as_of | retrieval timestamp + UNKNOWN + explicit retrieval-time basis |
| returned session/password/token or Set-Cookie | discarded, not persisted/exposed |

AAPL/VTI/QQQ/BRK.B synthetic tests use conid+currency+listing venue/classification. No ticker whitelist. IBKR BRK B becomes BRK.B via generic single-letter class separator, original broker symbol retained. No BRK truncation. Unknown or unsupported derivative/classification/venue, conflicting mapping/currency, incomplete identity -> UNRESOLVED. Broad STK may be refined by existing canonical ETF/STOCK metadata, never broker holdings→strategic allocation. Explicit secdef type COMMON/STOCK/ETF required for new resolution; unsupported type not guessed.

PAPER/LIVE broker source, quality UNKNOWN/DELAYED/STALE and separate DEMO market/FX are distinct. UI presents MIXED DATA MODE / VALUATION NOT LIVE; financial totals unavailable if any inventory/evidence cannot be trusted. Existing manual/DEMO portfolio preserved; both namespaces may be visible in this deliberately mixed local test workspace, never represented as real Owner net worth.

[Positions](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/portfolio/positions), [cash ledger](https://www.interactivebrokers.com/docs/web-api/trading/portfolio-and-positions/querying-currency-balances), [contract definition](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/contract/search-the-security-definition-by-contract-id). Checked2026-10-06. Field availability and class metadata need actual Paper verification before extending coverage.
