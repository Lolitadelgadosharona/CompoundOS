# ADR 0006: Decision Journal Backend Transactions

- Date: 2026-07-16
- Status: Accepted for Sprint 002 Slice 3B

## Context

The approved Decision Journal schema (ADR 0005) requires a backend workflow that
preserves Draft concurrency, immutable Confirmed snapshots, append-only
Corrections, atomic Draft discard with identity deletion, and audit redaction
without implementing a frontend or investment decision logic.

## Decision

- Use strict Pydantic contracts that forbid undeclared fields, trim Decision
  text, enforce Unicode code-point length limits, and validate ISO dates
  mechanically (no future decision_date, impossible dates rejected; review_date
  allows future).
- Keep SQLAlchemy queries in a Decision repository and transaction ownership in
  a synchronous Decision service.
- Lock Policy before Decision before Draft whenever multiple rows are involved.
  This ordering prevents deadlock with concurrent Policy publish.
- Confirm requires all four mechanical fields (title, decision_summary,
  rationale, decision_date) plus the current Published Policy Version ID. The
  request Policy Version ID must match the re-read current Published Version
  after locking Policy.
- Discard atomically deletes both the Draft row and the Decision identity row
  in the same transaction when the Decision has never been Confirmed
  (OD-S3-13 Option A). The AuditEvent retains the stable Decision UUID.
- Corrections use full replacement snapshots with per-Decision sequential
  numbering computed as MAX(correction_number) + 1 under the Decision row lock.
  selected_policy_version_id, archive metadata, and prior Corrections are not
  correctable.
- Map only explicit lifecycle/revision conflicts and approved named constraint
  violations to 409. Propagate unrelated database errors without masking.
- Allow Audit metadata only for changed_fields, draft_revision,
  policy_version_number, and correction_number. Never include Decision text,
  Correction text, Policy text, or correction_count.
- Materialize mutation response data from scalar values inside the locked
  transaction; do not re-query business data after commit.
- Cursor-based pagination for Decision audit events uses
  before_sequence_number + limit (default 50, max 100), querying DESC and
  returning ASC.
- List endpoint hides Archived by default; supports status filter and
  cursor/limit pagination.

## Consequences

- Competing mutations serialize through consistent row-lock order (Policy →
  Decision → Draft) and stale requests fail deterministically without partial
  state.
- Failed Confirm, Discard, Archive, or Correction transactions roll back
  completely; the database session is reusable.
- Atomic identity deletion ensures no orphan Decision rows exist after Discard
  of a never-Confirmed Draft.
- Append-only Corrections preserve the original Confirmed snapshot permanently;
  the effective view reflects the latest Correction.
- Decision APIs remain local-only and non-advisory; they do not create a
  complete user experience without separately authorized Slice 3C frontend
  work.
- Real PostgreSQL tests remain required for locking, triggers, rollback,
  concurrency, and deferred constraint behavior; mocks and SQLite cannot
  replace them.
