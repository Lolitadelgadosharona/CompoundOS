# Migration plan

Sprint001: NO MIGRATIONS. Code foundation is disconnected from production/Preview financial records. Canonical ledger, Asset UUID, immutable Policy, decisions and demo database remain unchanged.

Before real writes, Owner reviews incremental schema proposal for connection/sync/provenance and source constraints. Existing Position source enum-like CHECK excludes fidelity; add compatible source via explicit migration only after design/approval. Existing account-provider uniqueness must be checked against tenant/connection scope; external record global uniqueness is insufficient for all brokers. Reject broker sync without approved account reconciliation. No auto promotion of DEMO IDs/data into LIVE.

Next authorized stage: fresh isolated DB schema rehearsal, fixture snapshots, canonical crosswalk verification, audit/redaction and durable idempotence/concurrency tests; backup/restore and rollback rehearsal. Then Owner official authorization and one read-only account pilot with current/last-known reconciliation, liabilities/margin/short support gate and full completeness checks. Strategic targets remain independently Owner approved; imported position never edits strategy. LIVE provider licensing/credentials/Committee readiness are separate release gates. No production migration or live connection authorized by this document.

Rollback now: revert only this uncommitted Sprint001 file delta after Owner review (preserve checkpoint769631a); no DB restore needed. Future live rollback must disable connector, revoke authorization and preserve last-known audit/history; never erase broker observations to hide failures.
