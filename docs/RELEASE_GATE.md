# CompoundOS — MVP Release Gate

This document defines the criteria a build must meet before an MVP
production release. Run each gate in order; the release is blocked if any
non-deferred gate fails.

---

## 1. MVP release criteria

A release is eligible when ALL of the following hold:

1. Full test suite passes except the three KNOWN DEFERRED failures below.
2. `ruff check` is clean.
3. The end-to-end business workflow test passes (mock AI).
4. Deployment config tests pass (`.env.example`, entrypoint, bootstrap).
5. A fresh install reaches `/api/setup/status = ready`.
6. Backup + restore drill completed successfully.
7. No secrets are committed (`.env` gitignored, placeholders only).

## 2. Test requirements

- `python -m pytest tests/ -q` → expect `1413 passed, 2 skipped, 3 failed`
  (the 3 failed are the deferred items below; any OTHER failure blocks).
- `ruff check .` → clean.
- `tests/test_e2e_workflow.py` → passes (full chain, mock AI).
- `tests/test_deployment_config.py` → passes.

## 3. Deployment requirements

- `docker compose up -d --build` → api/db/redis/caddy all `Up`.
- Migration-on-startup applies cleanly (`alembic upgrade head` via
  `scripts/entrypoint.sh`); no migration failure.
- `curl /health` and `/api/health/full` respond.
- `scripts/smoke_check.sh` passes (read-only checks).

## 4. Governance requirements

- First Owner API key created via the one-off CLI
  (`docker compose run --rm api python -m apps.api.bootstrap_key`) — no
  unauthenticated HTTP endpoint.
- All 7 prompt templates approved (draft → active) via
  `POST /api/prompts/{id}/approve`.
- `PermissionGate` wired and enforced (no LLM call without permission).
- Prompt approval is Owner-only (AI cannot approve).

## 5. Backup/restore requirements

- Daily backup scheduled (`scripts/backup.sh` via cron).
- A restore drill succeeded: decrypt a backup → restore → `alembic upgrade
  head` → verify `/api/setup/status` reports schema/owner/household intact.

## 6. Known deferred issues (non-blocking)

These three tests fail on purpose and are NOT release-blocking:

| Test | Reason non-blocking |
|------|---------------------|
| `test_alembic_revision_chain_valid` | Migration `0032` uses a 33-char revision id instead of the 12-char convention. It applies cleanly; this is a migration-history hygiene issue, not a runtime defect. Fixing it would require rewriting migration history (risky) — deferred. |
| `test_evidence_confidence_constraint` | An advisory evidence-confidence CHECK constraint mismatch. Does not affect the core Research→Decision→Learning flow. Deferred to a dedicated schema-hardening slice. |
| `test_small_position_no_warning` | Portfolio-concentration warning threshold is advisory (no action is blocked). Deferred pending a calibration pass. |

If a NEW failure appears in any of these three test FILES beyond the named
test, treat it as a regression (blocking) — the waiver covers only the
named test ids.

## 7. Additional deferred (non-blocking) items

- `apps/api/Dockerfile` still uses `CMD uvicorn` (dev image; the prod
  image uses the entrypoint).
- Caddy domain templating (`CADDY_DOMAIN` documented but not injected).
- Multi-replica migration strategy (entrypoint migration is single-instance).
- No CI/CD pipeline; no secrets manager (Vault).

## Release decision

After all gates pass, the Owner authorizes the release. The merge history
(linear squash commits) and this gate record serve as the audit trail.
