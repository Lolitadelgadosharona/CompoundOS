# ADR 0001: Frontend Framework and Package Manager

- Date: 2026-07-12
- Status: Accepted

## Context

An earlier planning assumption referenced Next.js 15. The validated Sprint 001
implementation instead uses Next.js 16.2.10 with TypeScript and already has an
npm lockfile. Sprint 001.1 must make the implemented toolchain explicit and
reproducible without introducing an unnecessary package-manager migration.

## Decision

- Use Next.js 16 for the frontend, currently pinned to version 16.2.10.
- Use TypeScript with strict type checking.
- Standardize on npm 10 with Node.js 22.
- Commit and use `frontend/package-lock.json`; CI installs with `npm ci`.
- Retain the current `frontend/` directory for Sprint 001.1.

## Rationale

The current Next.js 16 implementation builds and validates successfully. Keeping
the implemented major version avoids an unmotivated downgrade to the earlier
Next.js 15 draft assumption. npm is already in use and its lockfile supports
reproducible installation, so changing package managers would add risk without a
demonstrated technical benefit.

## Consequences

- Documentation, CI, and local development use npm consistently.
- Next.js and its matching ESLint configuration are pinned exactly; transitive
  dependencies remain locked by `package-lock.json`.
- Upgrading the Next.js major version or changing package managers requires a new
  reviewed decision.
- A possible later move from `frontend/` to `apps/web/` remains a backlog decision.
