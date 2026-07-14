# ADR 0003: Immutable Investment Policy Snapshots

- Date: 2026-07-14
- Status: Accepted for Sprint 002 Slice 2A

## Context

CompoundOS must preserve user-authored Investment Policy history without allowing
application defects or direct database writes to rewrite a published snapshot.
Slice 2A is limited to persistence and database enforcement; Policy services,
APIs, publication orchestration, and frontend workflows are not authorized.

## Decision

- Add explicit Alembic revision `0002_investment_policy_foundation` on top of
  `0001_household_persistence`; do not amend the merged Slice 1 migration.
- Store one stable Policy per Household and at most one editable Draft per Policy.
- Store immutable Version snapshots separately from editable Draft state, with
  lower-case `published` and `superseded` status values.
- Use `NUMERIC(5,2)` for user-authored target percentages and named database
  constraints for approved ranges, normalized names, ordering, and cardinality.
- Use a partial unique index to permit at most one current `published` Version per Policy.
- Use PostgreSQL triggers to allow only an otherwise unchanged sealing update and
  an otherwise unchanged `published` to `superseded` transition.
- Forbid every Version delete and every Version-allocation update/delete. Permit
  allocation insertion only while its parent Version is unsealed.
- Use a deferred constraint trigger to reject any transaction that would commit an
  unsealed Version. Failed snapshot construction is cleaned up by transaction rollback.
- Add `audit_events.sequence_number` as a database-generated, unique, monotonically
  increasing insertion sequence. It may contain rollback gaps and is not a global
  concurrent transaction commit order.
- Keep SQLAlchemy mappings aligned with the migration and validate all guarantees
  against real PostgreSQL.

## Consequences

- Immutable history is protected independently of future service/repository code.
- Snapshot construction has an internal unsealed interval that must begin and end
  inside one transaction; it is not a product lifecycle state.
- Direct SQL mutation attempts fail with stable trigger error identifiers.
- Development downgrade removes Slice 2A structures while preserving Slice 1
  tables and their pre-Slice-2A fields and rows.
- Policy use cases, API contracts, pagination, and frontend behavior require
  separately authorized later slices.
