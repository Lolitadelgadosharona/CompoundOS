# Data provider rights matrix

Checked2026-10-06; CONFIRMED means a public conditional permission/capability, not an active licensed CompoundOS entitlement. Every selected contract needs Owner review. No subscriptions purchased, commercial terms accepted or data API called. Prices/rights differ by exchange, billing interval, user classification and add-ons.

| Requirement | Twelve Data | Alpha Vantage | Massive |
|---|---|---|---|
| Production/API use | CONFIRMED conditional tier/fees; Owner action required | CONFIRMED personal/noncommercial conditional terms | CONFIRMED personal/nonbusiness conditional license |
| Personal/internal app | CONFIRMED scoped subscription internal use | CONFIRMED conditional personal use; business agreement required | CONFIRMED personal-only; business tier for others |
| US stocks/ETF quotes | OWNER ACTION REQUIRED coverage/entitlement/delay | OWNER ACTION REQUIRED real-time exchange entitlement | OWNER ACTION REQUIRED exchange/nonprofessional classification |
| Historical adjusted data | OWNER ACTION REQUIRED endpoint/tier/adjustment method | OWNER ACTION REQUIRED tier/adjusted access | OWNER ACTION REQUIRED adjustment/retention contract |
| FX USD/CNY | OWNER ACTION REQUIRED exact native pair coverage | OWNER ACTION REQUIRED FX endpoint coverage | UNCLEAR exact CNY coverage/product |
| Caching | CONFIRMED only within documented permitted timeframe | UNCLEAR | UNCLEAR |
| Retention | UNCLEAR durable evidence duration | UNCLEAR | UNCLEAR |
| Backup | UNCLEAR restore/termination rights | UNCLEAR | UNCLEAR |
| Derived calculations | CONFIRMED non-reconstructable derived data, tier restrictions | UNCLEAR durable derived-evidence rights | UNCLEAR precise use/redistribution classification |
| Owner display | CONFIRMED authorized-user display subject tier | CONFIRMED personal use subject terms | CONFIRMED sole personal use; others need business plan |
| External redistribution | NOT PERMITTED without add-on/written agreement | UNCLEAR; not authorized by personal grant | NOT PERMITTED by personal license |
| AI/LLM disclosure | UNCLEAR external processor/non-display permission | UNCLEAR | UNCLEAR this evidence workflow; provider MCP availability is not blanket permission |
| Immutable evidence retention | UNCLEAR especially termination | UNCLEAR | UNCLEAR |
| Attribution | OWNER ACTION REQUIRED tier/exchange requirements | OWNER ACTION REQUIRED applicable agreement | OWNER ACTION REQUIRED exchange/plan obligations |
| Commercial plan | OWNER ACTION REQUIRED internal/business classification | OWNER ACTION REQUIRED written commercial agreement | OWNER ACTION REQUIRED business plan if any other viewer |
| Monthly cost | UNKNOWN exact suitable total; Owner written quote required | UNKNOWN suitable premium/commercial total | UNKNOWN selected entitlement/business total |

Public pricing pages were inspected but did not expose reliable dollar totals in retrieved text; no invented monthly budget. Obtain quote covering necessary rights, rather than selecting an advertised entry price as sufficient. Yahoo authorization environment switch remains only a safety switch, not a license; Yahoo is not recommended as licensed production evidence source without explicit authorization.

TECHNICAL RECOMMENDATION: evaluate Twelve Data for both market/FX to reduce adapter maintenance; verify USD/CNY (not substitute CNH), adjusted historical completeness, timestamps, identity/search and rights before implementation. RIGHTS/LICENSE CONFIRMED FOR COMPOUNDOS: NO. Market and FX interfaces remain independently replaceable.

Sources:
- [Twelve Data terms](https://twelvedata.com/terms) §§2–3: conditional internal processing/storage/display and non-reconstructable derived data; caching timeframes and additional exchange rights. [Pricing](https://twelvedata.com/pricing).
- [Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/): conditional personal noncommercial access. [Premium](https://www.alphavantage.co/premium/).
- [Massive market-data terms](https://massive.com/legal/market-data-terms-of-service): personal nonbusiness license. [Own-app classification](https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app), [FAQ](https://massive.com/knowledge-base/categories/faq): additional viewers require business classification; development is not automatically exempt.

Launch gate: no reliable quotes/FX/evidence retention/LLM authorization => NOT READY for real recommendations. Offline code/testing readiness cannot clear this gate.

[Twelve Data official Forex overview](https://twelvedata.com/forex) documents exchange_rate/time_series capabilities; this supports technical evaluation, not verified native CNY coverage or retention entitlement.
