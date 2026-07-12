# Architecture

## Overview

CompoundOS will use a modular monorepo with a Next.js frontend, a FastAPI backend, PostgreSQL, Redis, Docker-based local development, and future decision-support services.

## Current Sprint Architecture

- Frontend: Next.js 16.2.10 App Router application with TypeScript in `frontend/`
- Backend: minimal FastAPI service in `apps/api/`
- Data: PostgreSQL and Redis are planned but not connected in Sprint 001
- Local infrastructure: Docker-based development is planned; Compose is deferred
  until it can be validated in a Docker-enabled environment
- Validation: pytest and Ruff for the backend; ESLint, TypeScript, and the Next.js
  production build for the frontend

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
- Avoid speculative service logic in Sprint 001.

## TODO

- Add shared contracts between frontend and backend.
- Define deployment and environment strategy.
- Add and validate Docker-based local infrastructure.
- Decide whether to migrate `frontend/` to `apps/web/` in a later approved sprint.
