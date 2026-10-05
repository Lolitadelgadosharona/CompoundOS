# Canonical identity invariants

VERIFIED FACT: `instrument_resolver.identity_dimensions` defines symbol, exchange, asset type, currency, provider and provider identifier. Asset UUID is the ledger identity; instrument name is retained as descriptive provider metadata and is not a global uniqueness key. Provider mapping and canonical venue identity both acquire transaction locks before creation/reuse. Reused mappings must reconcile all identity dimensions with the existing Asset.

A matching ticker alone cannot resolve an unknown venue. Historical NULL exchange records require explicit reconciliation; they are not silently assigned a venue. Same symbol at different venues can represent distinct UUIDs when provider IDs distinguish them. Conflicting provider IDs, currency or class raise deterministic identity errors. BRK.B is preserved canonically and BRK-B remains its Yahoo identifier.

Research request parameters now persist canonical Asset UUID and the selected instrument metadata. Legacy requests stay readable but cannot become newly approvable without current canonical evidence.

Verification: collision/different venue/class-share tests use a real isolated PostgreSQL schema; Yahoo search and returned identities for nine requested symbols were also independently checked. This verifies technical response behavior, not authorization to retain or deploy those feeds.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
