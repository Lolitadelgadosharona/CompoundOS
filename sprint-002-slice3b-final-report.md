# Slice 3B Final Report — Decision Journal Backend Workflow and API

## Delivery Summary

| Field | Value |
|-------|-------|
| Slice | Sprint 002 Slice 3B |
| PR | #12 (squash merged) |
| Merge commit | `0d85a9d` |
| Merge time | 2026-07-16T14:25:36Z |
| Main CI (post-merge) | 3/3 SUCCESS (infrastructure, backend, frontend) |
| Push CI (pre-merge HEAD) | 3/3 SUCCESS |
| PR CI (pre-merge HEAD) | 3/3 SUCCESS |
| Total tests | 302 (102 non-PG + 138 PG + 62 frontend) |
| Branch | `sprint/002-decision-api` (deleted) |

## Commits on Branch (squashed into one merge commit)

1. `f14c131` feat: add Decision Journal backend workflow and API
2. `7e19606` test: cover Decision Journal transactions and concurrency
3. `8af311f` docs: record Sprint 002 Slice 3B implementation
4. `b9cc785` fix: address review findings M-1, L-1 through L-5, and session pattern
5. `92ec66c` fix: set sealed_at on test Policy Version for deferred trigger
6. `a5aa839` fix: use proper unsealed→published version lifecycle in test helper
7. `dc93a5f` fix: use Policy service functions for test version setup
8. `ae52c2f` fix: commit autobegin before Policy service calls in test setup
9. `4448739` fix: add required confirmation field to PublishPolicyDraftRequest
10. `a635c3c` docs: mark Slice 3B Done after CI verification (302 tests pass)

## Files Changed (14 files, +2933 / -8)

| File | Action |
|------|--------|
| `apps/api/decision_schemas.py` | CREATED — Pydantic request/response contracts |
| `apps/api/repositories/decisions.py` | CREATED — database queries with FOR UPDATE |
| `apps/api/services/decisions.py` | CREATED — atomic transaction services |
| `apps/api/routers/decisions.py` | CREATED — 12 FastAPI endpoints |
| `apps/api/main.py` | MODIFIED — router registration |
| `docs/ADR/0006-decision-journal-backend-transactions.md` | CREATED — ADR |
| `docs/ADR/README.md` | MODIFIED — ADR index |
| `docs/ARCHITECTURE.md` | MODIFIED — Slice 3B architecture |
| `docs/CHANGELOG.md` | MODIFIED — Slice 3B Complete |
| `docs/MASTER_PLAN.md` | MODIFIED — status update |
| `docs/PRD.md` | MODIFIED — status update |
| `README.md` | MODIFIED — Notes |
| `tests/api/test_decisions.py` | CREATED — 27 schema tests |
| `tests/test_decision_backend.py` | CREATED — 32 PostgreSQL tests |

## 12 API Endpoints

| Method | Path | Function |
|--------|------|----------|
| POST | `/api/decisions` | Create Decision Draft |
| GET | `/api/decisions` | List Decisions |
| GET | `/api/decisions/{id}/draft` | Read Draft |
| PATCH | `/api/decisions/{id}/draft` | Update Draft |
| POST | `/api/decisions/{id}/draft/discard` | Discard Draft |
| POST | `/api/decisions/{id}/draft/confirm` | Confirm Draft |
| GET | `/api/decisions/{id}` | Detail (original/effective snapshots) |
| POST | `/api/decisions/{id}/archive` | Archive |
| POST | `/api/decisions/{id}/unarchive` | Unarchive |
| POST | `/api/decisions/{id}/corrections` | Append Correction |
| GET | `/api/decisions/{id}/corrections` | List Corrections |
| GET | `/api/decisions/{id}/audit-events` | Audit Events (cursor pagination) |

## Review Findings Resolved

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| M-1 | MEDIUM | Unarchive endpoint used untyped Body | Fixed |
| L-1 | LOW | Unused PolicyVersionMismatchError class | Removed |
| L-2 | LOW | Unused CORRECTABLE_FIELDS tuple | Removed |
| L-3 | LOW | Unused get_decision without household filter | Removed |
| L-4 | LOW | E501 line too long in repositories | Fixed |
| L-5 | LOW | DecisionAuditEventResponse imported inside function | Moved to module level |

## CI Test Failures Resolved

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `policy_version_insert_invalid` (17 tests) | Test helper created InvestmentPolicyVersion in autobegin mode; BEFORE INSERT trigger requires explicit transaction | Use Policy service `publish_draft` which wraps `session.begin()` |
| `A transaction is already begun` (17 tests) | Autobegin transaction from `get_current_household` conflicted with Policy service's `session.begin()` | `session.commit()` before Policy service calls |
| `PublishPolicyDraftRequest` missing field | `confirmation: Literal[True]` required but not provided | Added `confirmation=True` |

## Architecture Patterns

- **Lock ordering**: Policy → Decision → Draft (prevents deadlock with Policy publish)
- **Atomic discard**: DELETE Decision + ON DELETE CASCADE removes Draft (OD-S3-13 Option A)
- **Correction numbering**: MAX+1 under Decision row lock (OD-S3-14)
- **Audit metadata allowlist**: changed_fields, draft_revision, policy_version_number, correction_number
- **Error contract**: 400 (no-op/incomplete), 404 (not found), 409 (stale/lifecycle/concurrent), 422 (schema/date/extra)
- **`_ensure_transaction`**: idempotent context manager for both API and test contexts

## Sprint 002 Status

| Slice | Status |
|-------|--------|
| Slice 1: Household Persistence | Done |
| Slice 2A: Investment Policy Persistence | Done |
| Slice 2B: Investment Policy Backend API | Done |
| Slice 2C: Investment Policy Frontend | Done |
| Slice 3 TD Gate | Done |
| Slice 3A: Decision Journal Persistence | Done |
| **Slice 3B: Decision Journal Backend API** | **Done** |
| Slice 3C: Decision Frontend | Not Authorized / Not Started |

## Untracked Files

39 review artifact files preserved, all SHA-256 hashes verified unchanged.

## Next Step

Slice 3C (Decision Frontend Workflow) is **Not Authorized**. Only the Project Owner can decide whether to authorize it.
