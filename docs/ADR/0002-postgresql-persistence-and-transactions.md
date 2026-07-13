# ADR 0002: PostgreSQL Persistence and Transactions

- Date: 2026-07-13
- Status: Accepted for Sprint 002 Slice 1

## Context

HouseholdProfile and its AuditEvent must persist across refreshes, enforce one
total household under concurrent creation, and commit business and audit writes
atomically. The existing FastAPI service has no persistence layer.

## Decision

- Use PostgreSQL as the only formal Slice 1 product store.
- Use synchronous SQLAlchemy 2.x sessions with the psycopg 3 driver. Do not mix
  synchronous and asynchronous database access.
- Keep one request-scoped session and place each create or actual update plus its
  AuditEvent in one short service-level transaction.
- Keep SQLAlchemy queries and record construction in small repository functions;
  keep commit/rollback ownership in the service transaction boundary.
- Use explicit Alembic migrations. The application must not create tables
  implicitly at startup. Compose uses a one-shot migration service before API start.
- Store only changed field names in AuditEvent metadata, never the full household
  values. The actor is the documented local-only constant `local-owner`.
- Enforce at most one HouseholdProfile with a database check and unique singleton
  sentinel. Convert a duplicate integrity failure to HTTP 409.
- Keep Redis in the development stack but use it for no Slice 1 product behavior.
- Run migration, repository, constraint, API, and transaction rollback tests
  against real PostgreSQL. SQLite and mocks cannot replace those tests.

## Consequences

- Database-backed requests are synchronous and intentionally small; no external
  calls occur inside their transactions.
- Both the HouseholdProfile write and AuditEvent write roll back if either fails.
- Alembic must reach head before the API can serve household requests.
- The initial migration supports a development downgrade, but no production-grade
  downgrade guarantee is made in this slice.
- psycopg binary packages are used for reproducible local and CI installation;
  production packaging remains outside this local-only slice.
- Changing the database driver, sync/async model, session boundary, migration
  strategy, singleton mechanism, or atomic-audit guarantee requires a new ADR.
