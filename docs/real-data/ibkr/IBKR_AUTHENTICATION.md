# Authentication/session boundary

Owner logs into the official local CPGW directly; CompoundOS never receives username/password, browser cookie, token or refresh secret. CPGW manages authentication upstream; requests use only User-Agent/Accept. Each HTTP client is short lived: no browser auth copied, cookie jar forwarded between requests or artifact persisted/exposed to frontend. Official User-Agent requirement is implemented.

CPGW login is manual on same machine; API requests must originate there. Official FAQ requires daily reauthentication. Expiry/restart/401/403 -> OWNER_REAUTHENTICATION_REQUIRED, last-known data preserved, no silent retry/reauth/escalation. No keepalive tickle, session initialization, browser credential automation or gateway logout API. Restart may require login again; server success is never fabricated from synthetic tests.

Paper login uses the separate Paper username; no live/Paper slider is guaranteed. Owner confirms Paper account references locally; never paste username/password/session into Codex/ChatGPT. The adapter requires DU+DEMO evidence, or DU plus exact locally Owner-confirmed Paper references for schemas whose type lacks DEMO. Account prefix/type are defensive checks, not a universally documented cryptographic mode assertion. Unknown mode fails closed. Live authorization cannot bypass a Paper-account mismatch.

CPGW has no TWS Read Only checkbox guarantee. The TWS setting does not apply to this Web adapter. CompoundOS's closed GET allowlist is its enforcement boundary. A manual gateway login may establish broker-side functionality; CompoundOS never calls /iserver to initialize or escalate it. Separate official authorization limitations remain.

[Gateway FAQ](https://www.interactivebrokers.com/docs/web-api/authentication/cpgw/client-portal-gateway-faq), [Paper login](https://www.interactivebrokers.com/docs/web-api/authentication/paper), [request requirements](https://www.interactivebrokers.com/docs/web-api/authentication/cpgw/request-requirements). Checked2026-10-06. Do not treat local safety flags as credentials or data licenses.
