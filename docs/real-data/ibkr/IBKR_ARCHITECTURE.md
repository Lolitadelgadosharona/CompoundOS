# IBKR read-only integration

Base2cc7571 on codex/compoundos-owner-preview. This Sprint chooses Client Portal Gateway (CPGW) rather than Sprint001's TWS technical candidate, following explicit Owner Sprint002 direction. No third-party broker wrapper, browser scraping, login automation, credential capture or trading session initialization.

Official endpoint allowlist (only GET, fixed local HTTPS /v1/api base):
- /portfolio/accounts — discovery, first call before account resources.
- /portfolio/{accountId}/ledger — native cashbalance/timestamp. BASE summary excluded.
- /portfolio/{accountId}/positions/{page} — pages start0, maximum100 rows/page; all pages must complete.
- /trsrv/secdef?conids={conid} — canonical contract definition and venue/currency, outside /iserver.

No /iserver, /tickle, /sso, /reauthenticate, /logout, order, transfer, settings, market quote/history, Flex or transaction endpoint. The official outer account-read session permits non-/iserver resources; desired endpoints that fail session/eligibility do not cause capability escalation. Accounts unavailable in this retail path or unknown account modes fail closed.

GatewayReader → InteractiveBrokersProvider → broker_foundation snapshot validation → existing canonical_asset within savepoints → normalized sync history → existing Account/Position/CashBalance projection. Owner-scoped and global gateway advisory locks serialize publication/reads; resolver writes, ledger replacement, sync record and AuditEvent share one transaction. Identity conflict becomes UNRESOLVED; malformed/incomplete batch becomes SYNC_FAILED. No strategy/policy/market-observation/transaction writes.

0037_ibkr_read_only adds2 new tables only: owner/mode connections, immutable sync_runs with sanitized typed snapshots, counters and actual start/end. FK RESTRICT, mode/identity immutable trigger, only enabled toggle permitted. No backfill, schema constraints on historical ledger unchanged. Account source interactive_brokers:paper/live, position/cash source interactive_brokers. Ledger history append-only except existing is_latest pointer semantics. Existing manual/DEMO rows not replaced.

New migration applied only to fresh isolated test databases, not running Preview/production. App0037 mutation/health gate requires0037; populated downgrade refused to prevent sync evidence loss. Empty downgrade removes only2new tables/functions. Existing0036 app mutation gate rejects0037 even though added tables preserve old columns: rollback needs forward-compatible app or backup/restore into separate DB, not blind downgrade. Owner reviews migration/recovery before any operational adoption.

Native Paper runner uses a separate Compose project with DB/Redis on loopback55474/55475 and native API8182/Web3882; CPGW/browser/API share the Mac host. It seeds a separate DEMO Preview namespace, never copies/promotes existing financial records. Runner is Owner-invoked and not executed during this Sprint. Stop the existing Preview before native build because frontend .next directory is shared. Original Preview volumes preserved; normal start script rebuilds correct3802/api mapping on return.

Technical adapter/read integration complete against synthetic official-shaped responses; real Paper/live gateway, TLS deployment and account completeness NOT VERIFIED. Real accounts require Owner action. LIVE default unavailable; separate explicit authorization flag plus account-mode evidence is required. New recommendations blocked whenever broker sync history exists; broker data alone never clears market/FX/identity/Policy/Committee gates.

Sources: [retail CPGW](https://www.interactivebrokers.com/docs/web-api/getting-started), [session separation](https://www.interactivebrokers.com/docs/web-api/authentication/sessions), [CPGW same-machine limits](https://www.interactivebrokers.com/docs/web-api/authentication/cpgw/limitations-of-the-client-portal-gateway). Checked2026-10-06. These are technical documentation, not production data-retention license evidence.
