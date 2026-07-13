# CompoundOS

CompoundOS is a long-term AI Family Office and Wealth Operating System. This Sprint 001 repository foundation establishes the project structure, documentation scaffold, local development workflow, minimal health endpoints, and validation tooling.

## Goals for Sprint 001

- Establish a clean monorepo foundation for future frontend, backend, data, and governance work.
- Document the long-term vision, architecture, and governance boundaries.
- Create a minimal, reviewable implementation with health checks and automated validation.

## Repository Layout

- apps/api: FastAPI backend service
- frontend: Next.js frontend application shell
- docs: product, architecture, and governance documentation
- tests: backend health tests

## Local Development

### Prerequisites

- Node.js 22.x
- npm 10.x (the repository standard; use the committed `package-lock.json`)
- Python 3.9 or newer

Sprint 001.1 uses Next.js 16.2.10 with TypeScript. See
`docs/ADR/0001-frontend-framework-and-package-manager.md` for the accepted version
and package-manager decision.

### Backend

1. Create a virtual environment: `python3 -m venv .venv`
2. Activate it: `source .venv/bin/activate`
3. Install dependencies: `python -m pip install -r requirements.txt`
4. Start the API: `python -m uvicorn apps.api.main:app --reload`

The backend is available at `http://localhost:8000`; its health endpoint is
`GET /api/health`.

### Frontend

1. Change directories: `cd frontend`
2. Install dependencies: `npm ci`
3. Start the development server: `npm run dev`

The frontend is available at `http://localhost:3000`; its health endpoint is
`GET /api/health`.

### Validation

- Backend lint: `ruff check apps tests/api`
- Backend tests: `pytest -q tests/api`
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

The Compose file and Docker build paths have been statically validated. Docker
runtime verification remains pending because Docker is not installed in the
current validation environment.

## Monorepo Convention

The current validated layout keeps the API in `apps/api/` and the web application
in `frontend/`. A possible migration from `frontend/` to `apps/web/` is deferred
to a separately approved sprint; Sprint 001.1 does not restructure working code.

## Notes

This sprint intentionally does not implement trading, broker integrations, authentication, or autonomous agents.
