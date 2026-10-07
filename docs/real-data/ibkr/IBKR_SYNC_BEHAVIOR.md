# Sync behavior

Only Owner SYNC NOW POST /api/investment/ibkr/sync {} causes broker reads. GET /connections and dashboard only read persisted data. Disconnect POST /api/investment/ibkr/disconnect {} toggles enabled false; an explicit next Sync action may reconnect. Never automatic polling, trading call or live connection during startup.

Every run has UUID, owner/mode connection, actual start/end, received/accepted/unresolved counts, sanitized error and normalized provenance snapshot. Account references preserved server-side, masked in UI. Global gateway + household locks serialize request/ledger updates. Complete pagination required; failure/expiry/rate limit/unknown currency/nonfinite amount/short exposure/incomplete balance rolls back resolver+ledger, appends failed run and retains last known portfolio. Older provider observation than previous accepted snapshot rejects.

Positions source stable account:conid, cash account:currency; native BASE summary excluded. Repeated successful sync appends point-in-time history while only one current set remains; current quantities never double count. Global legacy provider-account uniqueness cannot adopt another household's record. Canonical mappings preserve Asset UUID, currency/venue/class share and conid identity; collisions unresolved.

If any instrument unresolved, full normalized batch is retained for Owner display, previous published ledger retained, no partial trusted publication. All imported holdings shown with strategy target by canonical UUID; unconfigured target0/non-target. Strategy never modified. Avg cost optional; not quote/tax history.

CONNECTED/STALE/SYNC_FAILED/DISCONNECTED and unresolved count separate. Last successful sync independent of last attempt. Missing provider position timestamp -> UNKNOWN with retrieval-time basis, never fabricated provider as_of. Cash timestamp preserved; >24h displays STALE (existing valuation rule). Paper/live mode does not imply fresh/approved valuation. Broker history always adds NOT_LIVE valuation blocker in this Sprint; before a future trusted provider integration, no mixed inventory+DEMO prices recommendation.
