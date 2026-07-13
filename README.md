# CompoundOS

CompoundOS is a long-term AI Family Office and Wealth Operating System. Sprint
002 Slice 1 adds a local-only household recordkeeping workflow to the validated
Sprint 001 foundation.

> **Local-only security boundary:** This Sprint 002 build is for local,
> single-user development only. It has no authentication and must not be exposed
> to the public internet.

## Current Scope

- Create, read, and update the sole `HouseholdProfile`.
- Persist the profile and append-only `AuditEvent` records in PostgreSQL.
- Show the household summary and read-only audit timeline at `/household`.
- Keep all policy, allocation, journal, AI, Guardian, broker, trading, and
  authentication behavior out of Slice 1.

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

### Frontend

1. Change directories: `cd frontend`
2. Install dependencies: `npm ci`
3. Start the development server: `npm run dev`

The frontend is available at `http://127.0.0.1:3000`; its health endpoint is
`GET /api/health`, and the approved Slice 1 flow is at `/household`.

### Validation

- Database migration: `alembic upgrade head && alembic current`
- Backend lint: `ruff check apps tests`
- Backend tests: `TEST_DATABASE_URL="$DATABASE_URL" pytest -q`
- Frontend lint: `npm --prefix frontend run lint`
- Frontend type check: `npm --prefix frontend run type-check`
- Frontend tests: `npm --prefix frontend test`
- Frontend production build: `npm --prefix frontend run build`

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

This slice intentionally does not implement investment policy, target allocation,
decision journals, trading, broker integrations, authentication, Guardian logic,
or autonomous agents. Sprint 002 is not complete, and Slice 2 is not authorized.
