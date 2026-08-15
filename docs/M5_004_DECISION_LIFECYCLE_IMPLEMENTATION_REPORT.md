# M5-004 Decision Lifecycle Implementation Report

CompoundOS — End-to-End Decision Lifecycle Wiring
2026-08-14

Baseline: main 2d960e4 (M5-003 Production Hardening merged).

---

## 1. Summary

Wired the complete Decision Lifecycle: Research → Committee → Decision
Draft → Owner Approval → Journal → Learning Review → Provenance Trace.
Connected the previously-orphaned `decision_lifecycle.py` services to the
existing Decision Journal (`services/decisions.py`). No new features, no
architecture redesign, no migration.

## 2. Lifecycle flow validated

| Stage | Mechanism |
|-------|-----------|
| Research → Committee | `CommitteeIntegrationService.complete_research()` links memo → committee session + evidence (now preserves `run_id` + `symbol` in structured_facts) |
| Committee → Decision Draft | NEW `DecisionBridgeService.create_decision_draft()` reuses journal `create_decision` + `update_draft` with minimal mapping |
| Owner Approval | `OwnerDecisionService.approve()` flows draft → confirm → snapshot (no bare `proposed` row) |
| Journal | `confirm_draft()` creates `decision_confirmed_snapshots` |
| Learning | `approve()` auto-triggers `schedule_reviews()` (30/90/365 days) |
| Provenance | `ProvenanceService.trace()` rewritten to Decision → Draft → Memo → Perspectives → LLM Execution → Evidence |

Minimal draft mapping:
- title = "{symbol} investment decision"
- decision_summary = committee recommendation
- rationale = memo thesis
- risks_and_uncertainties = memo risk factors
- evidence_or_sources = research_run_id

## 3. Files changed

- `apps/api/models.py` — ORM drift fix (add 'proposed' to decisions status CHECK)
- `apps/api/services/decision_lifecycle.py` — wiring (bridge + approval + trace)
- `tests/test_decision_lifecycle.py` — updated fixtures + 3 new tests

## 4. Database migration status

NONE. No migration, no schema change. Only code-level ORM alignment to
migration 0032 (which already added 'proposed' to the DB CHECK).

## 5. Tests

- Targeted (decision modules): 111 passed
- Full suite: 1325 passed, 2 skipped, 3 failed
- The 3 failures are pre-existing and unrelated (33-char revision id 0032,
  evidence confidence constraint, portfolio concentration).
- +3 net new tests vs M5-003 baseline (1322 → 1325).
- New integration test proves the full chain end-to-end with mock data.
- ruff: clean. No real AI calls.

## 6. Security review

- No secrets / API keys / credentials.
- No .env, no broker, no trading, no Investment Policy modification.
- Approval gated by Owner auth middleware; AI cannot invoke in production.

## 7. Remaining gaps

1. `committee_outcomes.decision_draft_id` not back-filled (journal deletes
   draft on confirm → FK would dangle); provenance traces via run_id instead.
2. Journal assumes a singleton household (`get_household_id`).
3. HTTP entry point still a simulation (`pipeline_async`).
4. `reject()` leaves a fully-populated draft (no "rejected" journal status).
5. Pre-existing 33-char revision id `0032_decision_lifecycle_hardening`.
