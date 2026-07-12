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
- Frontend production build: `npm --prefix frontend run build`

## Environment Variables

Copy `.env.example` to `.env` and adjust values if needed. The example contains
development-only placeholders and no real secrets.

## Local Infrastructure

PostgreSQL, Redis, and Docker-based development are architectural targets. A
Compose configuration is intentionally deferred until it can be validated in a
Docker-enabled environment.

## Notes

This sprint intentionally does not implement trading, broker integrations, authentication, or autonomous agents.
