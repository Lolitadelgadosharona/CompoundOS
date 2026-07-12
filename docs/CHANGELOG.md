# Changelog

## [Unreleased] - Sprint 001.1

### Changed

- Isolated CompoundOS in a dedicated Git repository directory without changing
  unrelated parent-directory files
- Standardized the frontend on Node.js 22, npm 10, TypeScript, and pinned
  Next.js 16.2.10
- Documented the current `frontend/` plus `apps/api/` monorepo layout
- Added ADR 0001 for the frontend framework and package-manager decision

### Delivery

- Corrected the Sprint 001 commit to use the approved repository-local Git identity
- Verified the intended GitHub repository is empty before initial push
- Draft pull request and GitHub Actions validation are pending

## [0.1.0] - 2026-07-11

### Added

- Initial monorepo structure for frontend and backend
- Documentation foundation for vision, roadmap, architecture, and governance
- Minimal FastAPI health endpoints
- Automated health tests and linting configuration
- CI workflow for backend and frontend validation
- Minimal Next.js application shell and web health endpoint

### Deferred

- Docker Compose configuration, pending validation in a Docker-enabled environment
