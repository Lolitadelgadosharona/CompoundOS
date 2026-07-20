# CompoundOS

CompoundOS is a long-term AI Family Office and Wealth Operating System for
personal, local, single-user use. Sprint 005 adds Data Orchestration: automated
Guardian scheduling, Worker execution, and the /automation dashboard.

> **Local-only security boundary:** This build is for local, single-user
> development only. It has no authentication and must not be exposed to the
> public internet.

## Current Scope

- Create, read, and update the sole `HouseholdProfile` at `/household`.
- Author Investment Policy Draft text and target allocations at `/policy`;
  publish immutable Version snapshots.
- Record Portfolio holdings through `/portfolio` with decimal precision,
  draft/confirm lifecycle, and snapshot history.
- Create and manage Decision Journal entries at `/decisions`.
- Configure Guardian monitoring checks at `/guardian`; run evaluations.
- **Schedule automated Guardian evaluations at `/automation`** — daily
  schedules with IANA timezone, created disabled by default, requiring
  explicit enable.  Manual one-shot triggers, run history, Worker status.
- A standalone Worker process connects directly to PostgreSQL (not HTTP).
- 431 PostgreSQL / 136 non-PostgreSQL / 217 frontend test baseline.
- Keep broker, trading, recommendation, market data, AI/LLM, and
  authentication behavior outside the current implementation.

## Repository Layout

- apps/api: FastAPI backend service
- frontend: Next.js frontend application (App Router)
- migrations: explicit Alembic database migrations (0001–0011)
- docs: product, architecture, and governance documentation
- tests: backend health, API, validation, migration, and PostgreSQL integration tests

## Automation (/automation)

The Automation workspace lets the Owner create daily schedules for Guardian
evaluation.  Schedules are **created disabled** — enable them explicitly after
review.  The Worker process connects directly to PostgreSQL; it never calls
the FastAPI HTTP server.

### Schedule lifecycle

1. Create a schedule (job type, execution time, IANA timezone)
2. Review and **explicitly enable** the schedule
3. The Worker picks up due schedules and executes them
4. View run history and attempt details in the dashboard
5. Disable or delete schedules at any time

### Manual trigger

Use "Trigger run now" on a schedule detail to create a one-shot manual run.
This creates a new Run — it never modifies existing Run history.

### Worker

The Worker runs as a separate process (`python scripts/worker.py` or via
launchd).  The `/automation` page shows Worker status (read-only) —
it does **not** start, stop, or restart the Worker from the browser.

### Database safety

The test database name **must end with `_test`** (e.g., `compoundos_test`).
Destructive tests are rejected against non-test databases.  Run the full
PostgreSQL suite with:

```
COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1 \
TEST_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/compoundos_test" \
DATABASE_URL="$TEST_DATABASE_URL" \
pytest -q -m postgres
```

Never run destructive tests against the `compoundos` development database.

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
execute anything.

### Frontend

1. Change directories: `cd frontend`
2. Install dependencies: `npm ci`
3. Start the development server: `npm run dev`

The frontend is available at `http://127.0.0.1:3000`; its health endpoint is
`GET /api/health`, the Household flow is at `/household`, and the local-only
Investment Policy workflow is at `/policy`.

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

Slice 3B implements the Decision Journal backend workflow and API. It does not
implement the Decision frontend, trading, broker integrations, authentication,
Guardian logic, recommendations, or autonomous agents. Sprint 002 is not
complete; Slice 3B is in Review and Slice 3C is not authorized or started.
