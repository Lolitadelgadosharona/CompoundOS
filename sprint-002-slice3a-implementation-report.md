# Sprint 002 Slice 3A: Decision Journal Persistence — Implementation Complete

## Status: In Review (Draft PR #11)

PR: https://github.com/Lolitadelgadosharona/CompoundOS/pull/11
Branch: `sprint/002-decision-persistence`
Base: `main` at `6b9383f77692d1846cb3407fd094598255f1de5a`
Head: `7f455ec8aac700e9da76ccda91db0114caaaa223`
CI: All 6 checks SUCCESS (infrastructure, backend, frontend × push + pull_request)
Run ID: 29493826164 (PR), 29493823031 (push)

## Commit Chain

| # | SHA | Description |
|---|-----|-------------|
| 1 | `403e52a` | feat: add Decision Journal persistence schema |
| 2 | `c03ca4f` | test: verify Decision Journal persistence invariants |
| 3 | `0713e3f` | docs: record Sprint 002 Slice 3A implementation |
| 4 | `37b9f53` | fix: deferred trigger INSERT-only and update tests |
| 5 | `bec5665` | test: use engine connections for deferred trigger |
| 6 | `fb52dc5` | test: add db_session fixture for cleanup |
| 7 | `7afb1ee` | fix: deferred trigger queries current row state |
| 8 | `926fed3` | test: fix remaining test assertions |
| 9 | `7f455ec` | test: simplify policy version update test |

## Files Created/Modified

### New Files
- `migrations/versions/0003_decision_journal_foundation.py` — 4 tables, 5 trigger functions, 6 triggers (including CONSTRAINT TRIGGER DEFERRABLE INITIALLY DEFERRED)
- `tests/test_decision_journal_persistence.py` — 60 test functions covering migration, schema, data model, lifecycle, discard, snapshot immutability, corrections, and trigger inspection
- `docs/ADR/0005-decision-journal-persistence-and-immutability.md` — ADR for Decision Journal persistence design

### Modified Files
- `apps/api/models.py` — Added Decision, DecisionDraft, DecisionConfirmedSnapshot, DecisionCorrection ORM classes
- `tests/conftest.py` — Expanded TRUNCATE to 11 tables
- `tests/test_policy_migrations.py` — Updated HEAD_REVISION to 0003
- `tests/api/test_households.py` — Added 4 decision journal tables to approved tables set
- `docs/MASTER_PLAN.md` — Added Slice 3A status
- `docs/CHANGELOG.md` — Added Slice 3A entry
- `docs/ARCHITECTURE.md` — Added Slice 3A architecture section
- `docs/ADR/README.md` — Added ADR 0005 to index

## Decision Journal Tables (4)

1. `decisions` — stable identity, lifecycle status (draft/confirmed/archived), archive fields
2. `decision_drafts` — one-to-one with decisions, text fields with length constraints, revision tracking
3. `decision_confirmed_snapshots` — immutable, references policy_version, decision_date validation
4. `decision_corrections` — append-only, per-decision correction numbering, actor validation (local-owner only)

## Trigger Functions (5)

1. `fn_decision_identity_lifecycle` — BEFORE UPDATE: validates status transitions, archive field rules, immutability of id/household_id/created_at
2. `fn_decision_identity_delete_guard` — BEFORE DELETE: only draft decisions can be deleted, no snapshots allowed
3. `fn_decision_confirmed_snapshot_immutability` — BEFORE INSERT/UPDATE/DELETE: blocks all modifications, validates required fields on insert
4. `fn_decision_correction_immutability` — BEFORE INSERT/UPDATE/DELETE: blocks update/delete, validates actor/status/ownership/snapshot existence
5. `fn_decision_lifecycle_consistency` — AFTER INSERT (deferred): validates snapshot/draft consistency with decision status at COMMIT time

### Critical Fix: Deferred Trigger

The deferred trigger initially used `NEW.status` which holds the original INSERT values. If a row was inserted as 'draft' and then updated to 'confirmed' in the same transaction, the deferred trigger still saw `status='draft'` at COMMIT time, causing false `decision_draft_has_snapshot` errors.

Fix: The trigger now queries the `decisions` table for the current status at COMMIT time instead of using the stale `NEW` record.

## Test Coverage (60 tests)

- Migration lifecycle: fresh upgrade, incremental upgrade, downgrade/re-upgrade
- Schema inspection: constraints, foreign keys, functions, triggers
- Data model: uniqueness, length constraints, date boundaries, timezone sensitivity
- Lifecycle consistency: valid transitions, forbidden transitions, archive/unarchive, deferred trigger
- Discard foundation: atomic delete, cascade, audit event stability, multi-row guard
- Snapshot immutability: insert valid, update/delete forbidden, multi-row, FK restrict, rollback
- Correction: insert valid, confirmed/archived allowed, draft rejected, update/delete forbidden, actor validation, ownership mismatch, duplicate numbers, sequential numbers, FK restrict, rollback
- Trigger inspection: deferred trigger properties, error identifiers, Slice 2A trigger preservation

## Untracked Files

35 untracked files preserved (SHA-256 unchanged from base commit).

## What ChatGPT/Codex Needs to Do Next

This is a persistence-only slice. No service layer, API endpoints, or frontend was created.

**Not authorized**: Slice 3A implementation is complete. Slice 3B (backend API) and Slice 3C (frontend) are NOT authorized. Only the Project Owner can authorize the next slice.

**For Slice 3B** (when authorized): Create service layer, API endpoints, and tests for Decision Journal CRUD and lifecycle operations, building on the persistence foundation established here.

**For Slice 3C** (when authorized): Create frontend pages and components for Decision Journal workflows.
