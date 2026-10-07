# Capabilities

AVAILABLE architecture: ACCOUNT_READ, POSITIONS_READ, CASH_READ, COST_BASIS_READ (reported avgCost when available; missing remains Unknown). No verified tax-lot basis claim.

UNAVAILABLE: ORDER_PREVIEW, ORDER_EXECUTE, TRANSFER, WITHDRAWAL. No execute/cancel/modify/order-preview method, queue or HTTP endpoint in adapter. Gateway transport exposes only allowlisted GET resources. No account settings/permission change.

TRANSACTIONS_READ not implemented: a suitable full-history endpoint/report contract would expand scope. Empty transactions in this adapter means not fetched, never complete history. Foundation validator requires transaction-read permission only when transactions are actually present; existing tests preserve rejection of reserved capabilities.

SyncNow is an explicit Owner read/import action; investment approval does not invoke broker sync/adapter. Existing approval remains Journal/manual plan only; when broker data exists, mixed/unresolved/stale valuation prevents trusted new approval. No automatically added strategic targets, even for imported AAPL/VTI/QQQ.

Read-only mode is independent of broker permissions; broader upstream capabilities do not become CompoundOS capabilities. Official portfolio endpoints may not be available to every account. No automatic brokerage session fallback.
