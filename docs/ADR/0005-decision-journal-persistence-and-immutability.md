# ADR 0005: Decision Journal Persistence and Immutability

- Date: 2026-07-16
- Status: Accepted for Sprint 002 Slice 3A
- Decision: Stable Decision Identity + Draft + Immutable Confirmed Snapshot +
  Append-Only Correction (Approach C) with database-enforced immutability
- Consequences: PostgreSQL triggers and deferred constraints enforce the
  Decision lifecycle, snapshot immutability, correction validation, and
  cross-table consistency without relying on application-level checks alone

## Context

Sprint 002 Slice 3 Technical Design Gate authorized the Decision Journal
data model, lifecycle, immutability, and concurrency patterns. OD-S3-1
through OD-S3-15 were all resolved by the Project Owner on 2026-07-16.
Slice 3A was separately authorized for persistence and immutability
foundation only.

The Decision Journal records what the owner types, confirms, archives, and
corrects. It does not evaluate, recommend, score, trade, or hold actual
financial data.

## Decision

### Four-table Approach C data model

1. `decisions` — stable identity with `status` constrained to `draft`,
   `confirmed`, or `archived`. `created_at` is immutable. `archived_at` and
   `archive_reason` are set during `confirmed→archived` and cleared during
   `archived→confirmed`.

2. `decision_drafts` — mutable working draft. UNIQUE on `decision_id` (at
   most one per Decision). ON DELETE CASCADE to Decision for atomic discard
   of never-confirmed identities.

3. `decision_confirmed_snapshots` — immutable point-in-time record. BEFORE
   trigger prohibits all UPDATE and DELETE. References current Published
   InvestmentPolicyVersion via RESTRICT FK.

4. `decision_corrections` — append-only full-replacement snapshot. BEFORE
   trigger validates Decision status, actor, correction number, and snapshot
   ownership. UPDATE and DELETE are unconditionally forbidden.

### Five PL/pgSQL trigger functions

- `fn_decision_identity_lifecycle`: permits only `draft→confirmed`,
  `confirmed→archived`, `archived→confirmed`. Protects `created_at`, `id`,
  and `household_id` from modification. Validates archive/unarchive field
  changes occur only during status transitions.

- `fn_decision_identity_delete_guard`: permits DELETE only when
  `status = draft` and no Confirmed snapshot exists.

- `fn_decision_confirmed_snapshot_immutability`: prohibits all UPDATE and
  DELETE. Validates required fields on INSERT.

- `fn_decision_correction_immutability`: prohibits all UPDATE and DELETE.
  Validates actor (`local-owner`), correction number (positive), Decision
  status (`confirmed` or `archived`), and snapshot ownership consistency.

- `fn_decision_lifecycle_consistency`: deferred CONSTRAINT TRIGGER that
  verifies at COMMIT time that `draft` status has a Draft row and no
  snapshot, while `confirmed`/`archived` has a snapshot and no Draft.

### Key constraints

- `decision_date` is DATE type with `<= CURRENT_DATE` enforced by named CHECK
  constraints on snapshots and corrections.
- Per-Decision correction numbering: `UNIQUE(decision_id, correction_number)`.
  Service computes `MAX+1` under Decision row lock; database does not claim
  gapless sequences.
- Draft-to-Decision FK: ON DELETE CASCADE for atomic discard.
- Snapshot-to-Decision FK: ON DELETE RESTRICT.
- Correction-to-Decision and Correction-to-Snapshot FKs: ON DELETE RESTRICT.

## Consequences

- Database-level enforcement is the primary immutability guarantee; direct SQL
  cannot bypass triggers.
- Multi-row UPDATE and DELETE statements on protected tables fail if any row
  triggers a constraint violation.
- The deferred consistency trigger fires at COMMIT time, enabling multi-step
  transactions (delete Draft, insert snapshot, update status) without
  intermediate-state violations.
- Atomic discard of never-confirmed identities is supported by the
  Draft CASCADE FK and the DELETE guard trigger.
- Confirmed and archived identities cannot be deleted; the snapshot and
  corrections remain permanently.
- Slice 3A provides only the persistence layer. Decision service workflows,
  API endpoints, and frontend pages are deferred to Slice 3B and Slice 3C.
