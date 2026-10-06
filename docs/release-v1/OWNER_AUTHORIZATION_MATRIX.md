2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# Owner authorization matrix

| Requirement | Technical status | Terms/license status | Exact Owner action | Launch blocker |
|---|---|---|---|---|
| DeepSeek | REQUIRED; unavailable credentials; code/unit/integration verified | Account/open-platform disclosure/retention not confirmed | Configure secret/model/positive rates; run real verification and production-path Committee | YES |
| Market quotes | Registered adapter validates normalized identities/freshness; production source blocked | Yahoo automated access/actual Finance license not established | Obtain written applicable permission or select licensed equivalent; do not enable switch merely to pass tests | YES |
| Instrument search | Dynamic provider candidates/reconciliation tested | Same Yahoo access question | Cover search/metadata/identifier persistence and venue/class mappings in authorization | YES |
| FX | Pair/currency/freshness/inverse conversion tested | Same source-use/retention question | Cover CNY/USD and other actual pairs, timestamps, retention and AI sharing | YES |
| Historical market data | Optional Alpha Vantage research; no new backtest feature | Actual use class/subscription/retention unconfirmed | Leave AV_API_KEY absent until authorized, or obtain written applicable rights | NO if optional source remains disabled; YES if used |
| AI evidence usage | Exact deterministic packet/preview/citations tested | Market-to-LLM disclosure and AI input handling unconfirmed | Confirm both source supplier permissions and AI provider data processing, review exact privacy preview | YES |
| Evidence retention | Normalized/derived records persist; no automatic authoritative TTL | Permanent/backup retention not established | Obtain license covering current retention, or keep feed disabled pending separately reviewed retention contract | YES |
| Logs | Usage/auth/action logged, no API key logging intended; platform TTL UNKNOWN | Owner security operations policy not configured | Configure redaction/access/log rotation and retention in actual staging/production | NO separate code blocker; production runbook prerequisite |
| Decision Journal | Immutable original snapshots/links/manual plan verified | Owner-created history; provider-derived portions inherit rights questions | Approve retention of personal history; ensure provider data rights above | NO separate blocker; underlying rights remain YES |
| AuditEvent | Append-only/sequence/historical retention verified | Owner/internal audit plus inherited source content | Restrict access, encrypted backups; no automatic history deletion | NO separate code blocker |

No purchase, subscription upgrade, term acceptance or provider correspondence is performed here. Yahoo switch/Alpha Vantage key are operational controls, not licenses. A family-office/entity deployment may differ from private individual use. Contact provider licensing/support with exact categories/usage; any commercial, exchange-entitlement, attribution or retention obligation must be documented rather than guessed.

Secret handling: macOS Keychain or deployment platform secret manager; inject `COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1` with DeepSeek secret into API runtime. Model/rates are nonsecret configuration. Never send secrets in Git, chat, PR or shell arguments.

Verification after Owner configuration: run supplied real-provider verification on synthetic evidence, then `/api/investment/refresh`, candidate, committee-preview, Owner-consented committee and approval in isolated staging; inspect Journal/Audit and assert no transactions. See PRODUCTION_RUNBOOK and DeepSeek note for exact endpoint bodies. Successful HTTP calls do not settle license questions.
