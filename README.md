# CompoundOS

CompoundOS is a long-term AI Family Office and Wealth Operating System. Sprint
002 now includes the local-only Household workflow and the Slice 2B Investment
Policy backend API on top of the validated foundation.

> **Local-only security boundary:** This Sprint 002 build is for local,
> single-user development only. It has no authentication and must not be exposed
> to the public internet.

## Current Scope

- Create, read, and update the sole `HouseholdProfile`.
- Persist the profile and append-only `AuditEvent` records in PostgreSQL.
- Show the household summary and read-only audit timeline at `/household`.
- Record user-authored Investment Policy Draft text and target percentages through
  the backend API, then publish immutable Version snapshots.
- Keep Policy frontend, journal, AI, Guardian, broker, trading, recommendation,
  and authentication behavior outside the current implementation.

## Repository Layout

- apps/api: FastAPI backend service
- frontend: Next.js frontend application shell
- migrations: explicit Alembic database migrations
- docs: product, architecture, and governance documentation
- tests: backend health, API, validation, migration, and PostgreSQL integration tests

## Local Development

### Prerequisites

- Node.js 22.x
- npm 10.x (the repository standard; use the committed `package-lock.json`)
- Python 3.9 or newer
- PostgreSQL 16 for local database-backed API work, or Docker with Compose

Sprint 001.1 uses Next.js 16.2.10 with TypeScript. See
`docs/ADR/0001-frontend-framework-and-package-manager.md` for the accepted version
and package-manager decision.

### Backend

1. Create a virtual environment: `python3 -m venv .venv`
2. Activate it: `source .venv/bin/activate`
3. Install dependencies: `python -m pip install -r requirements.txt`
4. Copy `.env.example` to `.env`, then export it for the current shell with
   `set -a; source .env; set +a`.
5. Apply the explicit migration: `alembic upgrade head`
6. Check the migration revision: `alembic current`
7. Start the API: `python -m uvicorn apps.api.main:app --reload`

The backend is available at `http://localhost:8000`; its health endpoint is
`GET /api/health`.

The application never creates tables implicitly at startup. Migration to Alembic
head is a required, separate step.

### Household API

FastAPI publishes interactive local API documentation at `http://127.0.0.1:8000/docs`.
Slice 1 exposes only:

- `POST /api/households` — create the sole profile; a later create returns 409
- `GET /api/households/current` — read the profile; returns 404 when absent
- `PATCH /api/households/current` — update approved fields; empty/no-op returns 400
- `GET /api/households/current/audit-events` — read the stable audit timeline

Request bodies reject undeclared fields. Responses use explicit schemas and do
not expose ORM-only singleton state.

### Investment Policy API

Slice 2B exposes the local-only backend contracts documented by FastAPI at
`http://127.0.0.1:8000/docs`. The API supports the sole Policy and Draft,
whole-collection allocation replacement, immutable publication, version reads,
and a Policy-filtered audit timeline under `/api/policies`.

Percentages are JSON decimal strings such as `"12.50"`. These endpoints record
only user-entered policy information; they do not evaluate, recommend, score, or
execute anything. No Policy frontend is included in Slice 2B.

### Frontend

1. Change directories: `cd frontend`
2. Install dependencies: `npm ci`
3. Start the development server: `npm run dev`

The frontend is available at `http://127.0.0.1:3000`; its health endpoint is
`GET /api/health`, and the approved Slice 1 flow is at `/household`.

### Validation

- Database migration: `alembic upgrade head && alembic current`
- Backend lint: `ruff check apps tests`
- Backend tests without a local PostgreSQL URL: `pytest -q` (the explicitly marked
  PostgreSQL integration suite is skipped)
- Real PostgreSQL tests: `TEST_DATABASE_URL="$DATABASE_URL" pytest -q -m postgres -ra`
- CI-equivalent PostgreSQL gate:
  `COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1 TEST_DATABASE_URL="$DATABASE_URL" pytest -q -m postgres -ra`
- Frontend lint: `npm --prefix frontend run lint`
- Frontend type check: `npm --prefix frontend run type-check`
- Frontend tests: `npm --prefix frontend test`
- Frontend production build: `npm --prefix frontend run build`

The project-specific required-mode flag intentionally fails when
`TEST_DATABASE_URL` is missing or empty. It prevents CI configuration regressions
from turning required PostgreSQL coverage into a successful skipped test run.

## Environment Variables

Copy `.env.example` to `.env` and adjust values if needed. The example contains
development-only placeholders and no real secrets.

## Local Infrastructure

The containerized local stack includes the Next.js frontend, FastAPI backend,
PostgreSQL, and Redis:

1. Copy `.env.example` to `.env` if local overrides are needed.
2. Validate the configuration: `docker compose config`
3. Build and start the stack: `docker compose up --build -d`
4. Check service state: `docker compose ps`
5. Verify `http://localhost:3000/api/health` and
   `http://localhost:8000/health`.
6. Stop the stack: `docker compose down`

Compose binds web, API, PostgreSQL, and Redis host ports to `127.0.0.1`. A
one-shot `migrate` service applies Alembic before the API starts. Redis remains
in the development stack but carries no Slice 1 product logic.

## Monorepo Convention

The current validated layout keeps the API in `apps/api/` and the web application
in `frontend/`. A possible migration from `frontend/` to `apps/web/` is deferred
to a separately approved sprint; Sprint 001.1 does not restructure working code.

## Notes

This slice intentionally does not implement a Policy frontend, decision journals,
trading, broker integrations, authentication, Guardian logic, recommendations,
or autonomous agents. Sprint 002 is not complete; Slice 2C and Slice 3 are not
authorized.
