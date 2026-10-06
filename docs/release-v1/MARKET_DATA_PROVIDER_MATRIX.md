2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# Production market-data provider matrix

VERIFIED FACT: only the factory-registered `yahoo_public` adapter currently supplies V1 instrument selection, normalized quotes and FX. No Folio service or licensed replacement adapter has been installed.

| Source / path | Categories / exact call | Cache / storage | AI evidence / display | Rights / launch |
|---|---|---|---|---|
| Yahoo `launch_providers.py` | `https://query1.finance.yahoo.com/v1/finance/search`; `/v8/finance/chart/{provider_id}?range=5d&interval=1d`; metadata, delayed quote, FX `{base}{quote}=X` | No in-memory/TTL HTTP cache. Canonical metadata/mapping persisted; normalized quote+identity in immutable market_observations; normalized FX in fx_rates. Full chart/search response discarded; five-day chart requested but bars not saved by this adapter. | Owner UI, valuation, candidate/Committee deterministic evidence. Normalized inputs/derived values retained without automatic expiry. | Public endpoints are not a production license. Configured production calls deny without switch. No access/LLM/retention authorization supplied; BLOCKER. |
| Alpha Vantage `research_evidence.AlphaVantageProvider` | `https://www.alphavantage.co/query`; OVERVIEW, TIME_SERIES_DAILY compact, INCOME_STATEMENT, BALANCE_SHEET; optional research | `AV_API_KEY`, no SDK. Parsed overview/OHLCV/financial DTOs; optional JSON cache (see retention note), research evidence/memos may persist normalized subsets. No automatic full raw HTTP-body persistence in adapter. | Optional legacy research evidence, may enter research LLM, retained research/memory. Does not replace V1 Yahoo pricing/FX. | Not configured here. Applicable individual/entity classification and subscription/permission must be verified before enabling; optional source can remain disabled. |
| Owner/manual/CSV import | Native cash, quantities, costs and reported values | Existing ledger/import/audit retained; cost estimate never becomes a live quote | Owner records and derived evidence; missing trusted quote blocks recommendation | Owner must have rights to uploaded statements/data; not a market-feed substitute. |
| Synthetic providers | Explicit test-only price/FX | Newly isolated test DBs only | Test evidence; test factories unavailable for production | No production launch fallback. |

`COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED=1` is only a safety switch. It does not grant a license. The [Yahoo general terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001) restrict automated collection without express prior permission. Applicable Finance/data supplier terms and access permission remain unresolved. We do not infer redistribution, financial entity use, AI disclosure or permanent evidence rights.

[Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/) distinguish individual noncommercial use and commercial/entity cases requiring written agreement. A paid plan/API key alone does not establish every data-use right. No commercial terms accepted or plan purchased. Owner needs written confirmation of the actual use class, exchanges, delays, rate limits, cache, retention, derived evidence, LLM sharing and redistribution.

No external news/macro adapter is wired by the current real evidence factory; corresponding cache categories/interfaces do not prove active providers. Research can separately route OpenAI/Anthropic/Google via its governed runtime; those are AI services, not market-price sources, and require their own data-disclosure permissions if enabled. Staging/production configuration was not available to prove which optional paths are enabled there.

## Final production-readiness field review

| Required field | Yahoo public V1 adapter | Optional Alpha Vantage research |
|---|---|---|
| Purpose/search/quotes/history/FX | Active factory for search, metadata, delayed quote and FX; chart requests5d bars but V1 stores only normalized metadata/latest quote | OVERVIEW, compact daily historical prices and statements; current research factory; not the V1 instrument/quote/FX factory |
| Production use status | Disabled by default; actual staging denied before external calls | Disabled in inspected environment; AV_API_KEY absent |
| API/license basis | Public HTTP endpoints, no applicable written permission supplied; safety switch is not license | Individual noncommercial license depends on actual use class; entity/commercial agreement not supplied |
| Retention restrictions | Exact applicable permission NOT VERIFIED; normalized price/FX/evidence/backup storage requires coverage | Exact account-specific cache/evidence/backup retention permission NOT VERIFIED |
| Redistribution restrictions | No unrestricted redistribution right established; Owner-only UI does not settle export/AI disclosure | Actual rights not established; do not assume external indirect access is allowed |
| AI/LLM restrictions | No market-to-LLM permission established | No account-specific AI/evidence-reuse permission established |
| Required attribution | UNKNOWN until applicable permission/agreement reviewed; no claim that none is needed | UNKNOWN for actual dataset/use class; check agreement/entitlements |
| Rate limits | No documented production quota/SLA established for this unofficial endpoint; code12s timeout and bounded candidate requests are not quota/SLA | Account/endpoint-specific limits must be confirmed; no paid entitlement available here |
| Commercial plan requirement | Cannot infer a suitable commercial plan/access grant from the public endpoint | Entity/commercial use requires appropriate written agreement; realtime/delayed price entitlements may need premium membership |
| Exact Owner action | Obtain express applicable access/use/retention/AI permission for these endpoints, or select a licensed source; do not flip switch as consent | Keep optional source off for V1 unless Owner obtains applicable agreement/key and confirms limits/retention/AI rights |

Owner/manual records and test-only synthetic sources are not licensed live market feeds. Manual imports retain costs/native amounts and provenance; cannot silently replace missing quote/FX. Test adapters cannot provide production trusted data.

## Smallest safe replacement recommendation

RECOMMENDATION, not implemented or purchased: first establish whether written permission can cover the currently wired Yahoo endpoints. If not, select one licensed provider and implement only the existing InstrumentProvider/MarketDataProvider/FXProvider contracts; retain CompoundOS UUID/ledger/valuation/Policy/Guardian/Committee/Journal. No architectural replacement, optimizer or broker is required.

A concrete candidate for Owner licensing review is EODHD's instrument/fundamental/quote/Forex/historical offering, with a personal All-in-One tier only if Owner's actual use qualifies, or an appropriate commercial agreement otherwise. The [official service](https://eodhd.com/) describes those categories; its [commercial versus personal guidance](https://eodhd.com/financial-apis/commercial-vs-personal-license-use) says displayed packages are personal-use offerings and commercial use needs separate review. This is a candidate, not proof that its plan permits permanent evidence storage, LLM disclosure, exchange attribution or the required identity/timestamp accuracy.

Before selecting: ask supplier to confirm VTI/QQQ/VXUS/SGOV/AAPL/BRK.B identity/venue/currency/type, delayed-versus-real timestamp, CNY/USD and inverse FX, supported units/GBp, required rate limits/attribution and written normalized/derived/backup/AI-use rights. Indicative pricing must remain correctly labeled and pass the existing readiness contract. No new adapter is added without Owner selection/permissions; candidate coverage is NOT VERIFIED.

Alpha Vantage is another possible limited adapter reuse because the research client already exists, but do not treat it as a ready instrument-master/quote/FX replacement. [Official premium guidance](https://www.alphavantage.co/premium/) and [API documentation](https://www.alphavantage.co/documentation/) require applicable price-data entitlements; metadata/ETF/class-share identity coverage and retention/AI rights still require verification. No automatic free/public fallback was enabled.
