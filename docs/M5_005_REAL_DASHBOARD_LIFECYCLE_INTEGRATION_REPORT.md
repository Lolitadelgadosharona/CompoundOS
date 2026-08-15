# M5-005 Real Operation Entry Layer — Implementation Report

CompoundOS — expose the Research → Committee → Decision lifecycle
through the Dashboard.

2026-08-15 · baseline main 3901bc1 (M5-004 merged).

---

## Summary

Replaced the hardcoded/simulated dashboard and research flow with the
existing real services. The dashboard now reads live database data, the
research workflow runs the real ResearchIntelligencePipeline (via a thin
factory), and research completion wires the full M5-004 lifecycle
(Research → Committee → Decision Draft), with owner-only approve/reject
actions.

## Architecture changes

- NEW `services/research_pipeline_factory.py` — single factory that builds
  `ResearchIntelligencePipeline` (injectable components; production builds
  real adapters, tests pass mocks). No duplicate pipeline.
- `services/pipeline_async.py` — `execute_pipeline` now runs the real
  pipeline in a background task with a fresh `SessionLocal` (never holds
  the request session across async work), then wires Research → Committee
  → Decision Draft.
- `services/decision_lifecycle.py` — added `OwnerDecisionService.
  confirm_decision` / `reject_decision` (journal confirm/discard for a
  worker-created draft).
- Dashboard routers read real data via `build_dashboard()` + new read
  helpers (`list_memo`, `list_pending_decisions_detail`,
  `list_decision_history`, `learning_metrics`, `allocation_context`,
  `last_research`).

## Database impact

NONE. No migration, no new tables, no schema change.

## API changes

- `POST /api/research/start` — repurposed: creates the idea→review→
  request→run FK chain and runs the real pipeline (was simulation).
- NEW `POST /api/decisions/{id}/approve` — owner-only journal confirm +
  learning reviews.
- NEW `POST /api/decisions/{id}/reject` — owner-only journal discard.
- dashboard_data endpoints return real data (template-compatible shapes).
- Owner boundary preserved via global X-API-Key auth middleware.

## UI changes

- `decisions.html` APPROVE/REJECT buttons now hx-post to the real
  endpoints (were dead `href="#"`).
- Other templates unchanged — only fed real context vars.

## Tests

- NEW `tests/test_dashboard_lifecycle.py` — 10 integration tests (factory,
  FK chain, full lifecycle, confirm/reject, read helpers) with mocks.
- Updated `test_dashboard.py` + `test_research_workflow.py` (DB fixtures,
  valid UUIDs, real-data assertions).
- Full suite: 1337 passed, 2 skipped, 3 failed (3 pre-existing, unrelated).
- ruff clean on all changed files. No real AI calls.

## Security

- No secrets / API keys / credentials.
- No broker/trading; no Investment Policy modification.
- Owner approval boundary preserved; factory fails closed without
  provider credentials.
