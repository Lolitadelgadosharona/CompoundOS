# Official broker comparison

Research date2026-10-06. VERIFIED = public official documentation; UNCLEAR = not established without approved portal/account. No credentials, scraping, API calls or terms acceptance. Owner usefulness depends on actual accounts, which are unknown.

| Dimension | IBKR | Schwab | Fidelity |
|---|---|---|---|
| Personal access | Official TWS/IB Gateway; account/region eligibility needs confirmation | Official Trader API Individual developer product | Fidelity Access permissioned sharing verified; direct retail self-service developer API NOT VERIFIED |
| Authentication | TWS official login/2FA; local socket. Web API separate gateway/session or approved OAuth route | OAuth2; developer app review/callback configuration required | Approved data sharing/partner authorization; Akoya bearer/refresh-token route |
| Read-only safety | Official TWS Read Only setting; enforce own method allowlist too | Read endpoints selectable; independently read-only granted scope NOT VERIFIED | Permissioned data partner route; rights/eligibility not established |
| Accounts | TWS managedAccounts; Web /portfolio/accounts, subaccounts | Account resource details gated by developer portal | Akoya investments account information |
| Positions | TWS reqPositions/position callbacks; Web portfolio positions | Positions schema/endpoint availability needs authenticated official documentation | Akoya investment details/holdings; coverage provider-specific |
| Cash/balances | TWS account updates/summary by currency; Web account summary | Balance fields in account product require portal verification | Akoya balance product/coverage must confirm |
| Transactions | TWS execution data is not complete cash-flow history; Flex/report route separately approved | Transaction endpoint, history limits NOT VERIFIED here | Partner transaction product/coverage NOT VERIFIED |
| Cost basis | Position average-cost semantics need contract/multiplier verification; not universal tax lots | Field completeness/tax lots NOT VERIFIED | Product entitlement and basis completeness NOT VERIFIED |
| Market data | Separate subscriptions/rights; never inherited as analytics license | Separate product/rights review | Sharing holdings does not grant quote/history rights |
| Test environment | IBKR paper environment; data/subscription differences must verify | Public paper/sandbox environment NOT VERIFIED | Partner sandbox exists only subject to onboarding; personal eligibility NOT VERIFIED |
| Rate limits | TWS pacing endpoint-specific; Web global/session constraints; exact selected API version to confirm | Actual app quotas NOT VERIFIED | Partner quotas contractual, NOT VERIFIED |
| Commercial restrictions | Official API license/third-party onboarding and exchange rules; review selected route | Developer agreements/app approval; review before acceptance | Approved partner/aggregator onboarding, not public account automation |
| Maintenance | Medium/high: asynchronous local gateway, sessions, crosswalk/history | Medium/high: OAuth lifecycle, gated schemas, app review | High: partner onboarding/contracts and coverage |

RECOMMENDED FIRST BROKER: IBKR TWS/IB Gateway READ ONLY, conditional on Owner having eligible account. This is a technical implementation recommendation, not license confirmation or authorization to connect. Full history requirements may change the chosen IBKR adapter strategy; no assumption that executions cover dividends/deposits/transfers.

Official evidence:
- [IBKR TWS introduction](https://www.interactivebrokers.com/docs/tws-api/doc/introduction): socket API/interface/language support.
- [IBKR official Read Only setup](https://interactivebrokers.github.io/tws-api/initial_setup.html): broker-side order rejection setting (older official documentation; reverify deployed TWS version before pilot).
- [IBKR account summary](https://interactivebrokers.github.io/tws-api/account_summary.html).
- [IBKR Web account/portfolio API](https://www.interactivebrokers.com/campus/ibkr-api-page/web-api-trading/).
- [IBKR session authentication](https://www.interactivebrokers.com/docs/web-api/authentication/sessions): Web read-only outer session differs from brokerage session.
- [Schwab official portal](https://developer.schwab.com/products/trader-api--individual%26gt%3B): individual developer/OAuth/trading product. Public detailed product route yielded empty content; no unofficial schemas used.
- [Fidelity Access](https://www.fidelity.com/security/fidelity-access-data-security): sharing authorization/revocation.
- [Akoya investments](https://docs.akoya.com/reference/investments), [Akoya overview](https://docs.akoya.com/): permissioned investment information/token boundary. This establishes a partner route, not access granted to CompoundOS.

Additional official findings: [current TWS changelog](https://www.interactivebrokers.com/docs/tws-api/changelog) says pacing is based on Market Data Lines/2; do not blindly hardcode the older50msg/s rule. [Flex report generation](https://www.interactivebrokers.com/docs/web-api/flex-web-service/using-flex-web-service/generate-the-report) and [token setup](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration/enable-and-create-access-token) establish an official reporting-token route for linked accounts, not an authorization already granted here. Flex calls put a token in query parameters: future HTTP telemetry must redact the entire query, including failure traces/proxy logs.
