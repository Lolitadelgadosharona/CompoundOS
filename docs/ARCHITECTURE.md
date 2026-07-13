# Architecture

## Overview

CompoundOS will use a modular monorepo with a Next.js frontend, a FastAPI backend, PostgreSQL, Redis, Docker-based local development, and future decision-support services.

## Sprint 002 Slice 1 Architecture

- Frontend: Next.js 16.2.10 App Router application with TypeScript in `frontend/`
- Backend: FastAPI routers, Pydantic contracts, a small service transaction layer,
  and SQLAlchemy repositories in `apps/api/`
- Data: PostgreSQL through synchronous SQLAlchemy 2.x and psycopg 3; Redis carries
  no Slice 1 product logic
- Local infrastructure: `compose.yaml` defines the web, API, PostgreSQL, and Redis
  services using Dockerfiles aligned with the current repository paths; runtime
  verification remains pending in a Docker-enabled environment
- Migration: explicit Alembic revisions in `migrations/`; application startup never
  calls `create_all`
- Validation: real PostgreSQL integration tests plus pytest and Ruff for the
  backend; Vitest, ESLint, TypeScript, and the Next.js production build for the
  frontend
- Safety constraints: Pydantic performs request validation and named PostgreSQL
  checks independently enforce the same character limits and currency format

## Module Boundaries

- `routers/households.py`: four approved HTTP contracts and status mapping
- `schemas.py`: strict request/response contracts and technical field limits
- `services/households.py`: create/update transaction boundaries and domain errors
- `repositories/households.py`: SQLAlchemy queries and minimal AuditEvent writes
- `models.py`: only `household_profiles` and `audit_events`
- `frontend/app/household/`: local-only create/read/update/audit workflow
- `frontend/lib/household-api.ts`: typed browser-to-API boundary

No Policy, Allocation, Journal, User, Account, AI, Guardian, Broker, or trading
module is created in Slice 1.

## Transaction Flow

1. FastAPI validates and sanitizes the request contract.
2. A request-scoped synchronous SQLAlchemy session enters one short transaction.
3. The service inserts or updates HouseholdProfile and flushes it.
4. The repository inserts an AuditEvent containing changed field names only.
5. Both writes commit together; any failure rolls both back.

The database singleton uses a required boolean sentinel constrained to true and
unique across `household_profiles`. It prevents concurrent requests from storing
two profiles; the API maps the resulting integrity conflict to HTTP 409.

Frontend household mutations and AuditEvent refreshes have separate outcomes. A
successful mutation updates the profile and exits edit mode even if the following
audit GET fails. The timeline retains prior data, shows an independent error, and
offers a GET-only retry; mutations are never automatically replayed.

## Migration and CI

Alembic revision `0001_household_persistence` upgrades an empty database and
creates only the two approved product tables. The initial downgrade is provided
for development, without promising a production downgrade strategy. CI starts an
isolated PostgreSQL 16 service, runs `alembic upgrade head` and `alembic current`,
then runs repository/API/rollback tests against that real database. SQLite and
mocks do not replace these integration tests. CI sets the project-specific
`COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1` gate and runs the `postgres`-marked suite
explicitly. A missing test database fails in that mode; local runs without a
configured PostgreSQL database may skip the marked integration suite.

## Local Network Boundary

Browser requests use `NEXT_PUBLIC_API_URL` to reach FastAPI. CORS permits only the
two local web origins. Compose publishes all four host ports on `127.0.0.1`; an
automated expanded-config check rejects broader default bindings. Containers may
listen on `0.0.0.0` internally. This is not authentication and is not suitable for
public deployment.

## Repository Layout Decision

The mixed `apps/api/` and `frontend/` layout is intentional for Sprint 001.1
because it is functional, small, and already validated. A future migration to
`apps/web/` and `apps/api/` would improve naming symmetry, but it is not required
for correctness and would add unnecessary review risk to this hardening sprint.
Any migration requires approval in a later sprint.

Frontend dependencies are installed reproducibly with npm and the committed
`frontend/package-lock.json`. Node.js 22.x and npm 10.x are the documented local
and CI toolchain.

## Principles

- Keep the initial architecture simple and reviewable.
- Favor explicit contracts and documentable boundaries.
- Avoid speculative service logic and future-slice abstractions.

## Deferred

- Complete full Docker application runtime verification in a Docker-enabled environment.
- Decide whether to migrate `frontend/` to `apps/web/` in a later approved sprint.
- Any later persistence, authentication, policy, journal, Guardian, AI, or broker
  architecture requires separate approval.
