# Historical performance foundation (design only)

Current holdings cannot generate historical TWR/IRR/CAGR/drawdown. No metrics fabricated or implemented.

Require immutable dated portfolio/account valuations with native values, base currency, FX/quote observation IDs, complete/unknown status, liabilities, fee/tax handling and corporate-action adjustments. Dated external cash flows carry time zone, settlement/trade dates, direction, native currency, conversion provenance and account transfer pair ID. Internal transfers cancel at portfolio scope; contributions/withdrawals do not. Transactions capture executions, dividends, interest, fees, reinvestments and corrections; no fake trade execution from approval. Cost basis is optional supplied amount with method/currency, not quote.

TWR chains subperiod returns around external flows; require start/end values and flow-time valuation or declared approximation. IRR/XIRR uses signed dated external flows plus terminal valuation, documents roots/no-root. CAGR requires compatible beginning/end values with flow treatment. Drawdown requires consistent adjusted daily NAV series and cannot interpolate unknown periods as valid. History/backfill rights and missing intervals explicit. Minimum future tables valuation_snapshots, valuation_components, external_cash_flows, transaction_corrections and corporate_actions; not created this sprint.
