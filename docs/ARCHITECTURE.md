# Architecture

## Overview

CompoundOS will use a modular monorepo with a Next.js frontend, a FastAPI backend, PostgreSQL, Redis, Docker-based local development, and future decision-support services.

## Current Sprint Architecture

- Frontend: minimal Next.js App Router application in frontend/
- Backend: minimal FastAPI service in apps/api/
- Data: PostgreSQL and Redis are planned but not connected in Sprint 001
- Local infrastructure: Docker-based development is planned; Compose is deferred
  until it can be validated in a Docker-enabled environment
- Validation: pytest and Ruff for the backend; ESLint, TypeScript, and the Next.js
  production build for the frontend

## Principles

- Keep the initial architecture simple and reviewable.
- Favor explicit contracts and documentable boundaries.
- Avoid speculative service logic in Sprint 001.

## TODO

- Add shared contracts between frontend and backend.
- Define deployment and environment strategy.
- Add and validate Docker-based local infrastructure.
