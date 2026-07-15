# ADR 0004: Investment Policy Backend Transactions

- Date: 2026-07-14
- Status: Accepted for Sprint 002 Slice 2B

## Context

The approved Policy schema requires a local-only backend workflow that preserves
Draft concurrency, immutable publication, audit redaction, and exact decimal
contracts without implementing a frontend or investment decision logic.

## Decision

- Use strict Pydantic contracts that forbid undeclared fields, trim Policy text,
  reject JSON numbers for percentages, and retain decimal strings at the API boundary.
- Normalize allocation display names with Unicode NFKC and whitespace collapse;
  use Unicode casefold only for the stored canonical uniqueness key.
- Keep SQLAlchemy queries in a Policy repository and transaction ownership in a
  synchronous Policy service.
- Lock Policy before Draft whenever both rows are involved. Use Draft revision
  checks for every editable mutation.
- Replace the complete Draft allocation collection atomically; do not add item
  CRUD or autosave.
- Publish by superseding the prior current Version, inserting and sealing one
  complete immutable snapshot, consuming the Draft, and writing AuditEvents in
  one transaction.
- Map only explicit lifecycle/revision conflicts and approved named uniqueness
  constraints to 409. Propagate unrelated database errors.
- Allow Audit metadata only for changed field names, Draft revision, source or
  published/superseded version number, and allocation item count.
- Materialize mutation response snapshots from scalar values inside the locked
  transaction, commit, and then return without post-commit Draft/allocation reads
  or lazy loading.
- Model Policy creation as an optional strict empty-object request so omitted and
  `{}` bodies are accepted while extra fields and non-object JSON are rejected.

## Consequences

- Competing mutations serialize through consistent row-lock order and stale
  requests fail without partial state.
- Failed publication is cleaned up exclusively by transaction rollback.
- Policy APIs remain local-only and non-advisory; they do not create a complete
  user experience without separately authorized Slice 2C frontend work.
- Real PostgreSQL tests remain required for locking, triggers, rollback, and
  concurrency behavior; mocks and SQLite cannot replace them.
- Deterministic barriers and transaction-stage failure injection cover lifecycle
  races, response snapshots, rollback completeness, and connection reuse without
  adding test-only production behavior.
