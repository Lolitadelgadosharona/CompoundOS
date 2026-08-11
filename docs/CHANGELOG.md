# Changelog

## Sprint 022 — Scale & Intelligence Enhancement — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Investment Knowledge Graph, Advanced AI
Committee, Portfolio Monitoring, and Family Office Layer.
CompoundOS now has an entity relationship graph, multi-model
AI debate with divergence detection, position monitoring
alerts, and multi-portfolio role-based access.

### Slice A — Knowledge Graph (a2811ad)
- Nodes + edges; append-only immutable history
- 4 edge types: BELONGS_TO, ANALYZED_IN, LED_TO, SUPERSEDES

### Slice B — Advanced Committee (a2811ad)
- Claude: Value+Risk+Policy, GPT-4o: Growth+Macro, Gemini: Fit
- Divergence detection >20pt; never forces consensus

### Slice C — Portfolio Monitoring (a2811ad)
- 6 triggers, 4 priority levels (critical/high/medium/low)

### Slice D — Family Office (a2811ad)
- Multi-portfolio (taxable/IRA/trust), owner/advisor roles

### 14 tests

## Sprint 021 — Real Operation & Calibration — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Decision Accuracy Expansion, Knowledge
Compounding, Real Portfolio Validation, and Workflow Automation.
CompoundOS now tracks decision outcomes, cross-references past
analyses, validates CSV portfolio imports, and provides workflow
reminders — without ever executing trades.

### Slice A — Portfolio Validation (d99b8d9)
- CSV import: 4 required + 4 optional fields
- Calculation verification: ±1% tolerance
- Non-USD currency flagging

### Slice B — Decision Accuracy (d99b8d9)
- Outcome tracking with direction_correct flag
- 3 metrics: direction accuracy, return, confidence calibration
- Perspective-level accuracy scoring

### Slice C — Workflow Automation (d99b8d9)
- Monthly snapshot (auto), research reminders (manual)
- Never auto-executes trades or decisions

### Slice D — Knowledge Compounding (d99b8d9)
- Cross-reference current thesis vs past memos
- Contradiction detection (BUY→SELL, confidence swing)

### 14 tests

## Sprint 020 — Production Hardening & Real Usage — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: AI Quality Calibration, Data Reliability,
Security Hardening, and Owner Experience. CompoundOS now has
confidence calibration, hallucination detection, provider health
monitoring, a 7-point security audit, and UX improvements.

### Slice A — Security (6874622)
- 7-point audit: deps, SQL injection, env vars, CORS, keys,
  rate limiting, error sanitization
- Pass/warn/fail scoring; production readiness flag

### Slice B — Reliability (6874622)
- 4 provider health monitors (latency + failure counts)
- Cache validation: fresh / stale / invalid
- Pipeline health: 5-component check

### Slice C — AI Quality (6874622)
- 5-run confidence calibration (±10 target)
- 3-layer hallucination defense: evidence → validate → flag
- Quality penalty for unverified claims

### Slice D — UX (6874622)
- Theme, font, keyboard shortcuts (6 keys)
- Loading states documentation
- Accessibility checklist (WCAG AA)

### 15 tests

## Sprint 019 — Investment Operating System — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Portfolio Review Workflow, Risk Monitoring,
Capital Allocation Assistant, and Family Office Reporting.
CompoundOS now has structured review cadences, stress scenario
modeling, capital deployment guidance, and professional reporting.

### Slice A — Review Workflow (ef0971b)
- Monthly review: 6 sections + decision history + stale detection
- Quarterly review: headline, findings, recommendations

### Slice B — Risk Monitoring (ef0971b)
- 4 stress scenarios: correction, rate, sector, recession
- 5 alert rules: position, sector, beta, drawdown, data stale

### Slice C — Allocation (ef0971b)
- Deploy guidance: ranked by confidence, allocation-aware
- Sell options: underperformer + tax flags
- Disclaimer: guidance only, not financial advice

### Slice D — Reporting (ef0971b)
- Monthly, quarterly, custom dashboard reports
- CSV export for external tools

### 15 tests

## Sprint 018 — Portfolio Intelligence Upgrade — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Advanced Portfolio Analytics, Benchmark
Tracking, Committee Enhancement, and Bond Intelligence.
CompoundOS now computes Sharpe ratio, max drawdown, and beta;
compares against S&P 500 and 60/40 benchmarks; generates
structured committee briefs with dissent tracking; and
analyzes Treasury bond ETFs.

### Slice A — Bond Intelligence (3607a8e)
- TLT, IEF, SHY: yield, effective duration, rate sensitivity
- Duration risk rating; portfolio-level rate impact summary

### Slice B — Advanced Analytics (3607a8e)
- Sharpe ratio, max drawdown, portfolio beta, annualized returns
- Ratings: excellent/good/adequate/poor, low/moderate/high

### Slice C — Committee Brief (3607a8e)
- Structured 1-page brief with 6 perspective votes
- Majority vote detection, dissent flagging

### Slice D — Benchmark Tracking (3607a8e)
- S&P 500 + 60/40 comparison with period scaling
- Beat/lag indicators per benchmark

### 14 tests

## Sprint 017 — Intelligence Expansion — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Research Quality Scoring, Research Memory
Evolution, Macro Intelligence, and Multi-Asset Intelligence.
CompoundOS now auto-rates memo quality, remembers past analyses,
tracks macro context, and supports ETFs alongside equities.

### Slice A — Research Memory (7fe18bf)
- Per-entity indexed, immutable snapshots, append-only
- Outcome attachment, summary retrieval

### Slice B — Multi-Asset (7fe18bf)
- ETF classification and detail (top 10, expense ratio, concentration)
- Stocks always supported; bonds/cash deferred

### Slice C — Macro Intelligence (7fe18bf)
- 6 core indicators: rates, yields, spread, VIX, sectors
- Facts-only context — no prediction

### Slice D — Quality Scoring (7fe18bf)
- 5 dimensions: completeness, evidence, balance, confidence, clarity
- Weighted scoring, labeled: Strong/Adequate/Needs Improvement
- Informational only — never gates memo access

### 15 tests

## Sprint 016 — Real World Operation & Calibration — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Daily Operating View, Owner Feedback, Learning
Loop, and Data Quality. CompoundOS now has a daily decision center,
owner feedback capture, prediction accuracy tracking, and data
freshness monitoring.

### Slice A — Owner Feedback (a018a02)
- 4-question form: thesis, evidence, confidence, would_act
- FeedbackService with summary metrics
- <30 seconds per memo

### Slice B — Learning Loop (a018a02)
- Direction accuracy: confidence≥50 + positive return = correct
- Confidence error: |confidence - (50 + return×5)|
- 30d check-in, 90d formal review

### Slice C — Data Quality (a018a02)
- 4 freshness rules: price 6h, overview 7d, financials 90d, news 24h
- Status: fresh / stale / missing
- Confidence impact scoring

### Slice D — Daily Operating View (a018a02)
- DailyBrief: pending decisions, research, portfolio warnings
- Guardian alerts, learning updates
- needs_attention flag

### 18 tests

## Sprint 015 — Real Usage Validation & Refinement — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Real Investment Case Validation, Dashboard Data
Integration, Async Pipeline Execution, and Personal Workflow Automation.
CompoundOS now has real data APIs, async research execution with
progress tracking, and a validation framework.

### Slice A — Validation (f48a891)
- ValidationService: 5-dimension quality evaluation
- 5 validation symbols: AAPL, MSFT, GOOGL, BRK.B, JNJ
- All memos pass through — Owner filters

### Slice B — Dashboard Data (f48a891)
- 6 API endpoints under /api/dashboard/
- Thin dashboard architecture — no business logic in templates

### Slice C — Async Pipeline (f48a891)
- 7 progress states: pending → collecting → running → generating → scoring → complete/failed
- FastAPI BackgroundTasks integration
- Progress polling endpoint

### Slice D — Workflow Automation (f48a891)
- Manual-only execution
- Dashboard badge notifications

### 23 tests

## Sprint 014 — CompoundOS V1 Usability — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Production Foundation, Owner Dashboard, First Real
Investment Workflow, and Portfolio Intelligence. CompoundOS is now a
deployable web application with an HTML dashboard for daily family
office operations.

### Slice A — Production Foundation (271761c)
- Dockerfile: multi-stage build, healthcheck, production defaults
- docker-compose.yml: API + PostgreSQL + Redis + Caddy
- Caddyfile: auto-HTTPS reverse proxy
- Backup script: pg_dump + gzip, 30-day retention
- Deployment guide: VPS setup, migrations, restore

### Slice B — Owner Dashboard (9d26b2e)
- 5 pages: Dashboard, Research, Memo, Decisions, Learning
- HTMX + Jinja2 + Pico.css — zero build step
- Dashboard: net worth, allocation, guardian alerts
- Research: symbol input, status tracking
- Memo: 11-section view with confidence
- Decisions: approve/reject, history
- Learning: prediction accuracy, perspective performance
- 9 tests

### Slice C — First Real Investment Workflow (65210fb)
- DashboardResearchService: create request, poll status, list recent
- POST /api/research/start endpoint
- Dashboard integration: HTMX form to API
- mutation_gate EXPECTED_HEAD 0031→0032 fix
- 9 tests

### Slice D — Portfolio Intelligence (271761c)
- PortfolioIntelligenceService: deterministic calculations
- Holdings, allocation, concentration (20%/40% thresholds)
- Impact projection for new positions
- Dashboard memo shows allocation/concentration warnings
- 14 tests

### Total: 41 tests across 4 slices
### No credentials, no broker, no trading

## Sprint 013 — First Real Investment Intelligence — COMPLETE (2026-08-11)

### Sprint Summary
4 slices delivered: Real LLM Provider Runtime, Real Research Evidence Layer,
Active Research Intelligence Loop, and Investment Committee Decision Lifecycle.
CompoundOS can now execute governed real LLM calls through provider-neutral
interfaces, collect real market data with provenance, generate structured
investment memos with deterministic confidence scoring, and record owner
decisions in the committee lifecycle.

### Slice A — Real LLM Provider Runtime (82bb43e, PR #94)
- LLMProvider Protocol + 3 adapters (Anthropic, OpenAI, Gemini/google-genai)
- ProviderRouter, GovernedLLMExecutor with 7-step chain
- ResponseValidator, retry 3× + fallback, auth fail-fast
- 27 CI-safe mock tests

### Slice B — Real Research Evidence Layer (4fe15ea, PR #95)
- AlphaVantageProvider + DatabaseKnowledgeProvider + CacheService
- Error normalization into CompoundOS-owned categories
- Graceful degradation with missing_sources
- 24 CI-safe mock tests

### Slice C — Active Research Intelligence Loop (f7c46ef, PR #96)
- MemoGenerator: 6 perspectives → 11-section Investment Memo
- ConfidenceEngine: deterministic 6-dimension scoring (not LLM-generated)
- ResearchIntelligencePipeline: end-to-end orchestration
- 22 tests (15 integration + 7 hardening)

### Slice D — Investment Committee Decision Lifecycle (df3e7bc, PR #97)
- CommitteeIntegrationService: memo → committee session + evidence items
- OwnerDecisionService: approve/reject with decisions table + audit logging
- LearningLoopService: 30d/90d/1yr outcome reviews + prediction accuracy
- ProvenanceService: Decision → Memo → Perspectives → Evidence chain
- Migration 0032: 4 CHECK constraints aligned (reversible)
- 12 tests

### Total: 85 tests across 4 slices
### No credentials, no broker, no trading, no autonomous AI decisions

## Sprint 012 — AI Runtime + Research Execution Engine — COMPLETE (2026-08-10)

### Implementation
- PR #96: `feat(intelligence): add active research intelligence loop`
- Squash merged as: `f7c46effa17eb68b918ec0b21fb3fbbef6c31764`

### MemoGenerator
- Synthesizes 6 perspectives into 11-section Investment Memo
- Uses governed LLM executor (PermissionGate→PromptGovernor→Router→Provider→Validator)
- Structured output: thesis, evidence, bull/bear case, risks, valuation, portfolio_impact, guardian_impact, committee votes, decision_context, invalidation_conditions

### ConfidenceEngine (deterministic)
- 6-dimension weighted scoring: evidence_quality, thesis_clarity, risk_completeness, policy_alignment, data_freshness, historical_precedent
- Not LLM-generated — system code owns the calculation
- model_version tracked for formula evolution

### ResearchIntelligencePipeline
- End-to-end orchestration: EvidenceCollector → PerspectiveExecutor → MemoGenerator → ConfidenceEngine
- Full provenance: perspectives → analyses → memo → confidence
- Partial failure: failed perspectives preserved, memo skipped if <6 succeed

### Hardening
- Governance bypass prevention verified
- Provenance chain: 6 perspectives in committee section, perspective_analyses persisted
- Confidence determinism: identical inputs → identical outputs
- Memo gate: all 6 required for memo generation

### Tests
22 tests (15 integration + 7 hardening)

## Sprint 013 Slice B — Real Research Evidence Layer — Done (2026-08-10)

### Implementation
- PR #95: `feat(evidence): add real research evidence layer`
- Squash merged as: `4fe15ea313b2d39f66bc994f502f99d38c0e8b97`

### AlphaVantageProvider
- Implements MarketDataProvider Protocol (Sprint 012-C)
- Plain REST API, no SDK coupling
- AV_API_KEY from environment only, fail closed, repr redacts
- Methods: get_overview, get_financials, get_price_history
- Error normalization: ConfigurationError, RateLimitError, ProviderTimeoutError, ProviderResponseError

### DatabaseKnowledgeProvider
- Reads investment_knowledge_memory: profiles, historical thesis, decisions, outcomes
- Read-only; AI cannot mutate prediction_accuracy

### Evidence Layer
- CacheService: TTL-based market_data_cache with ON CONFLICT upsert
- EvidenceCollector: integrates market + knowledge providers
- EvidenceSnapshot: research-time evidence persistence prototype
- missing_sources propagation on graceful degradation
- ProvenanceEnvelope on every evidence artifact

### Follow-ups
- COS-013-B-FU-M1: Immutable Research Evidence Snapshot Layer (future)
- COS-013-B-FU-T1: snapshot-cache refresh test (future)

## Sprint 013 Slice A — Real LLM Provider Runtime — Done (2026-08-10)

### Implementation
- PR #94: `feat(llm-runtime): add real LLM provider runtime`
- Squash merged as: `82bb43e9ae3799e73451a5fb4a9081101ee8d44b`
- Architecture review: CHANGES REQUIRED → hardening applied → APPROVED

### Provider Abstraction
- `LLMProvider` Protocol: provider-neutral interface, zero SDK coupling
- `AnthropicAdapter`: wraps `anthropic.Anthropic`, lazy import, fail-closed
- `OpenAIAdapter`: wraps `openai.OpenAI`, lazy import, fail-closed
- `GeminiAdapter`: wraps `google-genai` (new SDK), per-instance Client, no global state

### Governance Chain (7 steps)
- PermissionGate → PromptGovernor → ProviderRouter → Provider → ResponseValidator → Logger → (Store: caller)
- `ResponseValidator`: JSON schema, required fields, conviction_score [1-10]
- Hard enforcement: auth 401/403 fail fast, transient retry 3× (1s/4s/16s), provider fallback

### Provenance
- `ExecutionResult`: validated dict, actual provider/model, retries, fallback_used
- Fallback provenance: `llm_execution_log` records actual_model (not primary)
- Failed executions: `_log_failure` writes failure log with error detail

### Credential Security
- All keys from environment variables only
- `repr()` redacts keys, never logged, never in DB
- No committed `.env` files

### Tests
- 27 mock tests (CI-safe, no real API calls)
- Covers: routing, governance chain, validation 7×, retry+fallback, auth fail-fast,
  fallback provenance, failure logging, credential isolation, AI authority

## Sprint 012 — AI Runtime + Research Execution Engine — COMPLETE (2026-08-10)

### Implementation
- PR #92: `feat(tools): add tool interface foundation`
- Squash merged as: `1d73f84a15f817e8f19e0846ef649ffd8e6fbc5b`

### Provider Abstraction
- `MarketDataProvider`, `CompanyDataProvider`, `KnowledgeProvider`, `DocumentProvider` Protocols
- Zero SDK coupling — interfaces only, no provider implementations
- No API keys or external connections

### Evidence Collection
- Enhanced `EvidenceCollector` with provider injection (dependency injection)
- `CacheService`: TTL-based freshness checking via `market_data_cache`
- Cache-before-provider: fresh cache hits skip provider calls

### Provenance
- `ProvenanceEnvelope`: 6 mandatory fields on every evidence artifact
- Fields: source, provider, source_timestamp, retrieved_at, data_quality_status, provider_version

### Graceful Degradation
- External provider failure → `missing_sources` logged
- Portfolio/policy/guardian data always available internally
- No fabricated, guessed, or hallucinated data substitution

### Tests
- 11 PostgreSQL integration tests (cache hit/miss/expired, provider injection, graceful degradation, provenance)

## Sprint 012 Slice B — Research Execution Pipeline — Done (2026-08-10)

### Merge
- PR #85: `feat(security): add auth, audit and escalation foundation`
- Squash merged as: `ba5054b5b3266d283df9c375c947bea0f61b7a2c`
- Independent review: APPROVED after SECURITY HARDENING

### Authentication
- Global X-API-Key middleware applied to ALL non-health endpoints
- SHA-256 hashed key storage — plaintext never persisted
- Environment-based bypass: development/test only
- Fail-closed: missing/production/unknown ENVIRONMENT requires auth
- Key bootstrap CLI: `python -m apps.api.bootstrap_key`
- Key lifecycle: create → use → revoke → rotate

### Authorization
- Endpoint classification: PUBLIC / READ / OWNER_MUTATION / SYSTEM
- /health and /api/health remain PUBLIC
- All financial endpoints require X-API-Key in production

### Audit
- Immutable audit_log with BEFORE UPDATE/DELETE trigger
- Events: authentication.success, authentication.failure, owner.mutation, authorization.denied
- Key create, revoke, and bootstrap all audit-logged

### Escalation
- notification_escalation_rules table (schema only)
- No email/SMS/phone delivery

### Test Coverage
- 22 PostgreSQL integration tests (migration, auth env, key validation, lifecycle, audit, escalation)

### Sprint 010 — COMPLETE
All 4 slices merged: Committee Bridge, Guardian Intelligence, Dashboard+Learning, Auth+Audit

## Sprint 010 Slice C — Wealth Dashboard + Learning Loop — Done (2026-08-10)

### Merge
- PR #84: `feat(dashboard): add wealth dashboard and learning loop`
- Squash merged as: `558dbac0437ca62a819450cd5a9377828369e6c3`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP

### Dashboard API
- GET /api/dashboard: full wealth snapshot
- Net worth: multi-currency with unconverted currency flagging
- Allocation: by asset class, capital bucket, currency
- Policy compliance: bucket drifts, rule violations from Guardian events
- Risks: concentration risk, active Guardian events
- Pending decisions, idea summary, activity feed (20 items)
- Live computation — no caching

### Learning Loop
- Migration 0024_dashboard_learning: decision_reviews table
- decision_confirmed_snapshots extended: +4 review columns
- Review types: 30_day, 90_day, 1_year, manual
- High-impact threshold: 5% portfolio allocation
- Review completion: outcome notes, return %, compliance, lessons learned

### AI Authority
- Dashboard is read-only — AI never writes
- Learning loop is Owner-controlled
- No automatic investment decisions or trading

### Test Coverage
- 10 PostgreSQL integration tests

### Follow-ups
- COS-010-C-FU-M1: Replace dynamic sqlalchemy imports in router
- COS-010-C-FU-L1: Avoid duplicate position loading
- COS-010-C-FU-L2: Add review completion 409 test
- COS-010-C-FU-L3: Add positive high-impact test

## Sprint 010 Slice B — Guardian Intelligence — Done (2026-08-10)

### Merge
- PR #83: `feat(guardian): add guardian intelligence layer`
- Squash merged as: `414e38fcbc38525e7044f9a6761d4333b111cd06`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP

### Guardian Checks
- Migration 0023_guardian_intelligence: extended check_type CHECK (+5 types)
- `capital_bucket_drift` — actual vs policy target allocation
- `single_position_concentration` — single position > max % (default 20%)
- `sector_concentration` — sector > max % (default 40%)
- `exploration_capital_limit` — EXPLORATION bucket safety rail (default 10%)
- `data_quality_staleness` — stale position data (default 24h)

### Policy Integration
- Thresholds from policy_rules (rule_type → check_type mapping)
- Fallback defaults when no policy_rule exists
- Severity from policy_rule.severity

### BLOCK_RECOMMENDATION
- Critical Guardian events block new Committee review requests (409)
- has_active_critical_event() check in committee_bridge router
- Warning events do not block

### AI Authority
- Guardian reads portfolio and policy — never modifies
- No trade/order/rebalance code paths
- Owner remains sole decision authority

### Test Coverage
- 20 PostgreSQL integration tests: migration, loading, drift, concentration, staleness, block, policy override, severity

## Sprint 010 Slice A — Committee Integration Bridge — Done (2026-08-10)

### Merge
- PR #82: `feat(committee): add committee integration bridge`
- Squash merged as: `972bf24be3940096673b3b5ba9b5ccdfedcc7677`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (0 BLOCKER, 0 HIGH, 4 LOW)

### Bridge
- Migration 0022_committee_bridge: 1 new table + 1 CHECK extension
- `committee_review_requests`: bridges investment_ideas → committee_sessions
- Extended `committee_evidence_items.source_type` CHECK (+3 types)
- Owner-controlled review workflow: POST /api/ideas/{id}/request-review

### AI Authority
- AI CANNOT request review (CHECK constraint blocks 'ai_agent')
- Only owner/committee/guardian sources allowed
- RESTRICT FK prevents idea deletion with active reviews
- One active review per idea enforced at API layer

### Test Coverage
- 18 PostgreSQL integration tests: creation, lifecycle, authority, querying, schema

## Sprint 009 Slice D — Manual Import + Data Source Foundation — Done (2026-08-10)

### Merge
- PR #81: `feat(import): add manual import foundation`
- Squash merged as: `61e7a8c5d6778d8e542625b40453836b0831ca4d`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (1 MEDIUM, 3 LOW)

### Data Foundation
- Migration 0021_manual_import_foundation: 1 column + 1 trigger
- `assets.confidence`: verified/unverified enum for asset resolution
- `fn_transaction_immutability`: blocks UPDATE of core fields, blocks DELETE entirely

### Import Pipeline
- CSV parser: positions, transactions, cash balances (10 MB limit)
- Validators: field-level (currency, decimal, datetime), row-level (account, asset), cross-row (batch dedup)
- Asset resolver: ISIN → (symbol,exchange,currency) → create with confidence='unverified'
- Idempotency via existing (source, source_record_id) partial unique indexes

### Provider Interfaces
- AccountImporter, PositionImporter, TransactionImporter, BalanceImporter (Protocol classes, no implementations)

### API Endpoints
- POST /api/import/positions, transactions, cash-balances (OWNER auth)
- GET /api/import/sources, POST /api/import/sources

### Follow-ups
- COS-009-D-FU-L1: Atomic position import upsert (is_latest toggling)
- COS-009-D-FU-L2: Extend transaction immutability to price_currency, fee_currency
- SEC-002: Global authentication layer

### Test Coverage
- 30 PostgreSQL integration tests: parsing, validation, idempotency, provenance, immutability

### Sprint 009 Status
- Slice A: DONE (9f0ed00, PR #78) — Core Portfolio Schema
- Slice B: DONE (4a7312c, PR #79) — Investment Policy Enrichment
- Slice C: DONE (f87e4e8, PR #80) — Investment Idea + Decision Bridge
- Slice D: DONE (61e7a8c, PR #81) — Manual Import + Data Source Foundation
- Sprint 009: COMPLETE

## Sprint 009 Slice C — Investment Idea + Decision Bridge — Done (2026-08-10)

### Merge
- PR #80: `feat(investment): add investment idea decision bridge`
- Squash merged as: `f87e4e8a9da738e0df9d94d2c6ae8dc06d73ec1d`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (1 MEDIUM, 2 LOW)

### Investment Ideas
- Migration 0020_investment_idea_bridge: 2 tables + 1 trigger function
- `investment_ideas`: 6-status lifecycle (draft→under_review→approved/rejected/deferred/cancelled)
- `idea_status_history`: append-only audit via AFTER INSERT OR UPDATE trigger
- Confidence: HIGH/MEDIUM/LOW/SPECULATIVE
- Source: owner/committee/guardian/external

### Decision Bridge
- `decision_drafts` + `investment_idea_id` (nullable FK, SET NULL)
- `decision_confirmed_snapshots` + `investment_idea_id` (nullable FK, SET NULL)
- Chain preserved: Idea → Committee Review → Owner Decision → Snapshot

### Design Invariants
- No AI authority — Owner remains sole decision-maker
- No automatic status transitions (enforcement deferred to FU-M1)
- Decision journal immutability unaffected (additive column only)

### Follow-ups
- COS-009-C-FU-M1: Enforce lifecycle transitions before API exposure
- COS-009-C-FU-L1: Consider soft-delete for investment ideas
- COS-009-C-FU-L2: Remove or integrate unused ALLOWED_TRANSITIONS

### Test Coverage
- 27 PostgreSQL integration tests: creation, lifecycle, history, decision bridge, schema validation

## Sprint 009 Slice B — Investment Policy Enrichment — Done (2026-08-10)

### Merge
- PR #79: `feat(policy): add investment policy enrichment`
- Squash merged as: `4a7312c3307c7201cb145965c94234e7aba98d6b`
- Independent review: APPROVE (0 BLOCKER, 0 HIGH, 3 LOW)

### Policy Configuration
- Migration 0019_policy_enrichment: 2 tables + 2 trigger functions
- `policy_capital_buckets`: capital allocation targets per version/draft
- `policy_rules`: 7 extensible constraint types (max_position, concentration, etc.)
- Single-table draft/version pattern with mutual-exclusivity CHECK
- Version rows immutable via BEFORE UPDATE/DELETE triggers
- Draft rows mutable, CASCADE deleted on publish

### Design Invariants
- No hardcoded 95/5 — any bucket name/percentage accepted
- Rule types: 7 approved (incl. exploration_capital_limit)
- Severity: info, warning, critical per rule
- Bucket uniqueness per (draft_id, bucket_name) and (version_id, bucket_name)
- Version FK: RESTRICT prevents deletion with attached buckets/rules

### Guardian Compatibility
- Schema supports future drift detection without modifying Guardian
- No automatic actions — read-only data for evaluation

### Test Coverage
- 35 PostgreSQL integration tests: constraints, uniqueness, immutability, isolation
- Pydantic schema validation for buckets and rules

## Sprint 009 Slice A — Core Portfolio Schema — Done (2026-08-10)

### Merge
- PR #78: `feat(portfolio): add core wealth data foundation`
- Squash merged as: `9f0ed00dc7126285f1cbbaaa9a0089a607085212`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (1 HIGH, 1 MEDIUM, 3 LOW)

### Wealth Data Foundation
- Migration 0018: 6 new tables + 5 account extension columns
- `assets`: canonical instrument identity (ISIN, symbol/exchange/currency unique)
- `positions`: account × asset with source provenance, is_latest point-in-time history
- `cash_balances`: per-account per-currency cash with provenance
- `transactions`: 11 financial event types (BUY/SELL/DIVIDEND/DEPOSIT…)
- `fx_rates`: exchange rates with timestamped observations
- `data_sources`: lightweight provider registry
- Account extension: account_type, capital_bucket, currency, provider, provider_account_id

### Design Invariants
- Every external datum: source + source_record_id + observed_at + imported_at
- Provider facts never silently mixed with CompoundOS calculations
- Import idempotency: partial UNIQUE indexes on (source, source_record_id)
- NULL source_record_id allows multiple manual entries without blocking
- is_latest semantics: supersede-before-create preserves point-in-time history
- All FKs RESTRICT: financial history cannot silently disappear

### Test Coverage
- 50 PostgreSQL integration tests: constraints, FKs, provenance, idempotency, schemas
- Pydantic schemas with field validators for all 7 entities

### Follow-ups
- COS-009-A-FU-H1: Transaction immutability trigger before first connector
- COS-009-A-FU-M1: Atomic position upsert contract
- COS-009-A-FU-L1: cash_balances imported_at naming consistency
- COS-009-A-FU-L3: transactions(executed_at) index for large volumes

## Sprint 008 Slice C — Daily Schedules — Done (2026-08-09)

### Merge
- PR #74: `feat(automation): complete Sprint 008 Slice C daily schedules`
- Squash merged as: `49e3a2258d6f9063c28e7133eee5f60734f5e2b7`
- Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (0 BLOCKER, 1 HIGH fixed, 3 MEDIUM, 2 LOW)

### Daily Schedule Infrastructure
- Migration 0017: CREATE OR REPLACE FUNCTION expanding job_type allowlist for `backup.daily`
- Lazy seed: Guardian + Backup daily schedules, default disabled, idempotent
- Idempotency: `schedule_id` + schedule-local IANA timezone date in SHA-256 key
- Duplicate prevention: `ON CONFLICT (idempotency_key) DO NOTHING RETURNING id`
- Schedule-local date: worker computes from schedule's IANA timezone, not `UTC now.date()`
- `next_run_at` always advances, even on duplicate detection

### COS-008-C-HARDEN
- `_JobTypeExecutionNotSupported`: fail-closed guard before Phase A
- `backup.daily` execution: NOT YET IMPLEMENTED (raises explicit error)
- Unknown job types: fail closed (never fall through to Guardian)
- 6 regression tests: spy, explicit error, guardian ok, unknown fail-closed, side effects absent, run not completed

### Test Coverage
- `tests/test_slice_c_daily_schedules.py`: 617 lines, 18 tests (12 original + 6 COS-008-C-HARDEN)
- Allowlist, idempotency key, seed idempotency, ON CONFLICT transaction safety, timezone correctness
- All tests pass in CI with real PostgreSQL

### Frontend
- JobType union expanded: `backup.daily`
- Schedule UI: enable/disable + time/timezone picker in `/automation`

### Remaining Follow-ups
- M1: DELETE /schedules/{id} confirmation guard
- M2: Lazy seed on GET couples read with write
- M3: `validate_lease_for_commit` clock parameter cleanup
- L1: Allowlist drift test (Python vs DB trigger)
- TECH-001: Frontend audit cleanup (pre-existing npm audit failures)

## Sprint 005 Orchestration Corrective — Done (2026-08-09)

### Review and Merge
- PR #75: `fix(orchestration): harden fenced worker finalization`
- Reviewed HEAD: `8551acf4e306315d07703bba86ca92204ec7dd9e`
- Squash merged as: `16aa86b853a20afc532a5f3144c2f8eb539ef0da`
- Independent review gate: **APPROVE** — 0 BLOCKER, 0 HIGH, 2 MEDIUM, 4 LOW
- Post-merge CI 31318099840: backend SUCCESS (608 PG, 138 non-PG)

### Root Causes Fixed
- Child `return` inside context manager committed on fenced; now uses explicit commit/rollback + `_FencedError`
- Parent didn't commit before spawn — child couldn't see lease rows; now commits run/attempt/lease before `proc.start()`
- Heartbeat only updated `heartbeat_at`, never extended `expires_at`; now extends via `clock_timestamp()`
- Parent overwrote child's successful finalization with 'failed'; now reads DB for terminal state
- `finalize_run` rowcount=0 triggered fallback writes; now does `session.rollback()` and returns None
- Lock order undefined; now consistently `runs → leases → ALL attempts ORDER BY id`

### Production Changes
- `apps/api/services/orchestration_executor.py`: Phase A/B separation, `_FencedError`, structured diagnostics with sqlstate
- `apps/api/services/orchestration_worker.py`: `ReconciliationResult` frozen dataclass, `reconcile_after_child_exit()` with 40P01 retry, `_reconcile_attempt()` terminal-first logic, authoritative notification status
- `apps/api/services/orchestration_repository.py`: heartbeat extends `expires_at` via `clock_timestamp()`, removed application clock parameter

### Test Coverage
- `tests/test_corrective_orchestration.py`: 1285 lines, 12 tests exercising real PostgreSQL + multiprocessing
- `tests/test_retry_exhaustion.py`: 4 deterministic non-PG retry exhaustion tests
- `tests/test_reconciliation_outcomes.py`: table-driven 5-outcome + completed-no-run_failed regression
- Bidirectional `pg_blocking_pids` AND assertions, residual resource verification, forced-cleanup tracking
- `tests/test_slice_b_notifications.py`: updated stale-token assertion to v17 no-fallback-write contract

### Follow-up
- OM-001: MEDIUM/LOW cleanup items from independent review

## Sprint 007 — Personal V1 Hardening + Notification — Done (2026-07-22)

### Technical Design Gate (PR #50 follow-up)
- 15 Owner Decisions resolved: Personal V1 hardening, selective local notification
- Backup/export/health/notification scope defined; external services deferred to V2

### Slice A — Backup, Export & Recovery (PR #60, #61, #62, #63)
- PostgreSQL backup: pg_dump → age streaming, SHA256 integrity, manifest per backup
- Export service: JSON + CSV for all Owner-facing entities, 24h auto-delete
- Retention: 7 daily + 4 weekly + 12 monthly, last-healthy guard
- Restore verification to _test database only; launchd opt-in CLI
- Cloud-sync detection and blocking; age encryption fail-closed

### Slice B — Health Dashboard & Credential UX (PR #60–#63)
- 10 component health checks: database, migration head, backup, restore, worker, leases, guardian, credential, launchd, notification
- 5-state model: healthy/degraded/unavailable/stale/unknown
- Mutation gate: fail-closed middleware on DB/schema failure
- Worker heartbeat table (not MAX(started_at)); restore freshness via timestamp
- Backup artifact file existence check; 3 health endpoints (/live, /ready, /full)

### Slice C — Lightweight Notification (PR #64, #65)
- Migration 0015 (notification_foundation) + 0016 (notification_integrity)
- Notification events with source/severity/fingerprint/delivery_status CHECK constraints
- Notification preferences: quiet_hours, timezone, enabled, enabled_sources, enabled_severities
- Explicit opt-in: enabled=FALSE default; Owner must PATCH preferences to enable
- 4 API routes: GET /events, POST /events/{id}/acknowledge, GET/PATCH /preferences
- Household-scoped fingerprint v2: SHA256(v2:{household_id}:{source}:{event_type}:{severity}:{entity_id})
- PostgreSQL advisory-lock dedup (pg_advisory_xact_lock) with 24h window + severity escalation
- Quiet hours 22:00–08:00 default with critical bypass; IANA timezone support
- macOS AppleScript adapter: static "on run argv" script, subprocess.run shell=False, timeout=10
- Delivery truth: adapter unavailable → "unavailable", adapter failure → "failed", success → "delivered"
- API body privacy: preview (100 chars) in response, full body in DB only
- Structured notification templates: only approved (source, event_type) pairs
- Health service wired: run_all_checks dispatches on DEGRADED/UNAVAILABLE (fire-and-forget)
- Notification health: enabled+failure on macOS → DEGRADED (degrades overall); disabled/no-adapter → HEALTHY (no impact)
- Preferences singleton: UNIQUE INDEX ((1)) on notification_preferences
- Sharp 0.34.5 → 0.35.3 override (CVE-2026-33327, CVE-2026-33328, CVE-2026-35590, CVE-2026-35591)
- Guardian/committee/automation/backup notification sources: templates defined, not yet wired

### PR #65 Integrity Corrective
- Independent review: 13 findings (2 BLOCKER, 4 HIGH, 4 MEDIUM, 3 LOW) → all resolved
- Re-review: 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW
- Squash merge: 031ebdaed7a287d70287bacc5a55e62ff825ac2f
- Main CI run 29886582098: 3/3 success

### Final Test Baseline
- 552 PostgreSQL tests (COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1, 0 failed, 0 skipped)
- 134 non-PostgreSQL tests, 2 expected skipped
- 251 frontend tests (Vitest, 14 test files)
- ESLint --max-warnings=0, TypeScript --noEmit, Ruff clean, npm audit 0 vulnerabilities

## Sprint 006 — AI Investment Committee Foundation — Done (2026-07-20)

### Technical Design Gate (PR #50)
- 15 Owner Decisions resolved: AI Committee + Evidence combined sprint,
  provider-neutral (DeepSeek V1 only), deterministic evidence pipeline,
  single structured LLM call, 7 perspectives, manual-only, Draft-only
  Decision Journal integration, macOS Keychain credentials, 50K/8K/$1.00
  budget, all-or-nothing valid report, max 1 retry (transient only)

### Slice A — Persistence + Evidence (PR #51)
- Migration 0012 (additive): committee_sessions, committee_evidence_items,
  committee_reports (immutable), committee_outcomes (append-only)
- Named CHECK/UNIQUE constraints, immutability trigger, append-only trigger
- Evidence Packet Builder: deterministic extraction from Policy, Portfolio,
  Guardian Events, Decisions — category-level only, no holdings/quantities/prices
- SHA256 content hashing for integrity, evidence IDs, citation references
- 32 PostgreSQL persistence tests

### Slice B — Provider + Validator + Orchestration + API (PR #53)
- AIModelProvider interface + DeepSeek adapter (V1 only)
- Credential management: macOS Keychain → explicit env fallback → fail
- Provider Output Validator: JSON schema, citation, safety, language validation
- Committee orchestration: evidence→privacy preview→call→validate→persist
- 9 API endpoints under /api/committee
- Budget enforcement (50K/8K/$1.00), retry (max 1, transient only)
- FakeProvider for deterministic testing — no live LLM calls in CI
- 31 provider/validator/orchestration tests

### Slice C — Committee Frontend (PR #54)
- /committee workspace: session create, privacy preview, Owner confirmation,
  run committee, report with 7 perspectives, outcome recording
- Manual-only: no auto-trigger, no auto-run on load
- Evidence citations vs model inference labels
- Macro insufficient evidence flag
- recommended_direction neutral display (4 approved enum values)
- No Buy/Sell/Hold or trading language
- 25 new frontend tests (10 API client + 7 component + 8 expanded)

### CI Infrastructure Fix (PR #52)
- Fixed SQLAlchemy URL password redaction in CI tests
- Replaced 5 instances of str(engine.url) → engine.url.render_as_string(hide_password=False)

### Final Test Baseline
- 491 PostgreSQL tests (COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1, 0 skipped)
- 136 non-PostgreSQL tests
- 242 frontend tests (Vitest + shuffled)
- ESLint --max-warnings=0, TypeScript --noEmit, Ruff clean

## Sprint 005 — Data Orchestration Foundation — Done (2026-07-20)

### Technical Design Gate (PR #37, #38)
- 15 Owner Decisions resolved (daily-only, default-off, direct PostgreSQL Worker,
  atomic fenced commit, lease fencing v4, no HTTP loopback, no notifications)
- Sprint 005 Technical Design and Open Questions documents merged

### Slice A — Orchestration Persistence (PR #38, #39, #40, #41)
- Migrations 0008–0011: job_definitions, schedules, runs, attempts, leases
- Fencing token protocol (v1→v4): atomic takeover, expiry enforcement, window refresh
- CHECK constraints, UNIQUE constraints, partial indexes for overlap prevention
- PL/pgSQL trigger functions: lease takeover prevention, terminal immutability
- Idempotency key: SHA256(job_type || params || scheduled_date)

### Slice B — Worker + Backend API (PR #42, #43, #44, #45, #46)
- 9 Automation endpoints under /api/automation
- Standalone Worker with direct PostgreSQL connection (no HTTP loopback)
- Claim + execute per-schedule transaction isolation
- Lease TTL 60s / heartbeat 15s / max runtime 300s / graceful shutdown 30s
- Process timeout enforcement with real multiprocessing spawn→kill→rollback
- Stale-run recovery (reaper) with atomic FOR UPDATE claim
- Guardian transaction-neutral core: evaluate_core never commits
- Final lease FOR UPDATE at commit window only (not during evaluation)
- clock_timestamp() for definitive expiry validation
- Heartbeat not blocked during Guardian evaluation
- Both takeover race orderings verified (takeover-first, lock-first)
- Graceful shutdown: real multiprocessing terminate→kill→orphan check
- Released lease is terminal (takeover SQL guards released_at IS NULL)

### Slice B — PostgreSQL Isolation Stabilization (PR #47)
- Single function-scoped postgres_test_isolation fixture
- Table auto-discovery (inspect→get_table_names) replacing hardcoded lists
- connect_args timezone=UTC default
- All date-boundary tests use SET LOCAL + CURRENT_DATE from PostgreSQL
- 10/10 pre-existing cross-test failures eliminated
- Two direct-main review fixes recorded (393a20d)

### Slice C — Automation Frontend (PR #48)
- /automation workspace: schedule CRUD, manual trigger, run history, worker status
- 9-endpoint typed Automation API client with AbortSignal support
- Default disabled on create; explicit enable required; no auto-trigger on load
- Independent abort controllers: core/schedule/runs/worker
- 409 conflict preserves local input; neutral language throughout
- 217 frontend tests (19 API client + 15 component); full accessibility

### Final Test Baseline
- 431 PostgreSQL tests (COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1, 0 skipped)
- 136 non-PostgreSQL tests
- 217 frontend tests (Vitest + shuffled)
- ESLint --max-warnings=0, TypeScript --noEmit, Ruff clean

### Explicit Product Boundary (Sprint 005 Closeout)
- Personal-use-only product direction
- Schedule explicit opt-in / default off
- No notifications in Sprint 005
- No automatic Guardian schedule creation
- Worker direct PostgreSQL (not HTTP to FastAPI)
- Atomic fenced effect commit (Guardian + Automation in one transaction)
- PostgreSQL _test database isolation enforced
- Direct-main commit exception (393a20d) recorded; normal PR workflow resumed

## Sprint 003 — Portfolio Snapshot + Holdings Foundation — Done (2026-07-17)

### Slice A: Portfolio Persistence (PR #20, e9743a5)
- Alembic revision 0004: portfolios, portfolio_drafts, portfolio_draft_holdings,
  portfolio_snapshots, portfolio_snapshot_holdings
- Named CHECK and UNIQUE constraints on all five tables
- PL/pgSQL triggers: fn_portfolio_snapshot_immutability,
  fn_portfolio_draft_consistency, fn_portfolio_lifecycle
- SQLAlchemy ORM models aligned with migration
- 130 real PostgreSQL tests (0 skipped)

### Slice B: Portfolio Backend API (PR #21)
- Pydantic request/response schemas with decimal-string contracts
- Repository queries with FOR UPDATE support
- Service transaction boundaries with lock ordering (Household→Portfolio→Draft)
- 9 endpoints under /api/portfolio: POST /draft, GET, PATCH /draft,
  PUT /draft/holdings, POST /draft/confirm, POST /draft/discard,
  GET /snapshots, GET /snapshots/{id}, GET /audit
- Concurrency tests, rollback tests, revision conflict tests
- Portfolio-filtered AuditEvent reads
- Cash unit_price = 1.00 enforcement via migration 0005 (additive CHECK)
- Controlled status transition current→superseded via migration 0006 (additive)
- Future-proof JSONB row comparison in immutability trigger

### Slice C: Portfolio Frontend (PR #22, 0a841d4)
- /portfolio page with typed Portfolio API client
- All 18 UI states from Technical Design §11 covered
- BigInt-based client-side total_value estimation (non-authoritative)
- Decimal strings throughout API boundary; no Number/parseFloat
- Cash unit_price 1.00 with neutral technical hint
- Zero holdings warning with explicit confirmation
- 409 conflict preserves local input with explicit reload
- Separate abort controllers for core, history, audit, and snapshot detail
- Pre-confirm view state restoration for cancel from review
- 80 new frontend tests (55 API client + 25 component)
- Independent blind review: APPROVE WITH NON-BLOCKING FOLLOWUP
  (0 BLOCKER, 0 HIGH, 0 MEDIUM after fix; 2 LOW all resolved)
- CI: 6/6 checks green on final HEAD before merge

## [Unreleased] - Sprint 003 Slice B (In Review)

### Added

- Portfolio API: 9 endpoints under /api/portfolio
- Cash unit_price = 1.00 database CHECK constraint (migration 0005, additive)
- Controlled snapshot status transition current→superseded (migration 0006, additive)
- Future-proof JSONB row comparison in immutability trigger
- Comprehensive API, gate, trigger, migration, and concurrency tests

### Changed

- Portfolio status semantics: 'draft' = draft exists; 'active' = confirmed, no draft
- Snapshot current→superseded transition allowed per Owner Decision Option A

### Fixed

- 0004 snapshot immutability trigger: allowed controlled status-only UPDATE via 0006
- Deferred trigger active+draft semantics clarified per Owner Decision

## [Unreleased] - Sprint 002 Slice 3B Complete

### Added

- Twelve Decision Journal API endpoints on `apps/api/routers/decisions.py`:
  POST /api/decisions (create Draft), GET /api/decisions (list),
  GET /api/decisions/{id}/draft, PATCH /api/decisions/{id}/draft,
  POST /api/decisions/{id}/draft/discard, POST /api/decisions/{id}/draft/confirm,
  GET /api/decisions/{id} (detail with original/effective snapshots),
  POST /api/decisions/{id}/archive, POST /api/decisions/{id}/unarchive,
  POST /api/decisions/{id}/corrections, GET /api/decisions/{id}/corrections,
  GET /api/decisions/{id}/audit-events
- Strict Pydantic request/response contracts in `apps/api/decision_schemas.py`
  with extra=forbid, trim, Unicode code-point length limits, and mechanical
  ISO date validation (future decision_date rejected, review_date allows future)
- Decision repository in `apps/api/repositories/decisions.py` with FOR UPDATE
  support, cursor pagination, and per-Decision Correction numbering
- Decision service in `apps/api/services/decisions.py` with atomic transactions:
  Policy→Decision→Draft lock ordering, 13-step Confirm, atomic never-Confirmed
  Draft discard with identity deletion (OD-S3-13 Option A), full replacement
  Correction snapshots with MAX+1 numbering under Decision row lock
- Router registered in `apps/api/main.py` with existing localhost CORS pattern
- Decision Pydantic schema tests in `tests/api/test_decisions.py` (27 tests)
- Decision PostgreSQL backend tests in `tests/test_decision_backend.py`
  (32 tests covering creation, draft CRUD, confirm, discard, archive/unarchive,
  corrections, audit events, detail views, and Household timeline inclusion)
- ADR 0006 documenting the Decision Journal backend transaction patterns

### Boundaries

- Slice 3B adds no frontend, `/decisions` page, migration, dependency, Compose,
  CI, authentication, recommendation, Guardian, AI, Broker, trading, actual
  holdings, accounts, monetary data, or Slice 3C behavior.
- Slice 3C (Decision Frontend Workflow): Not Authorized, Not Started.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C, 3A, 3B remain Done.
- Slice 3B Decision Journal Backend Workflow and API: Done.
- CI: 6/6 checks pass (push + pull_request × infrastructure/backend/frontend),
  302 tests total (102 non-PostgreSQL + 138 PostgreSQL + 62 frontend).
- Slice 3C: Not Authorized, Not Started.

## [Unreleased] - Sprint 002 Slice 3A Complete

### Added

- Alembic revision `0003_decision_journal_foundation` creating four Decision
  Journal tables: `decisions` (stable identity), `decision_drafts`,
  `decision_confirmed_snapshots`, and `decision_corrections`
- Five PL/pgSQL trigger functions: identity lifecycle transitions, identity
  delete guard (draft-only DELETE), confirmed snapshot immutability,
  correction immutability with status/ownership validation, and deferred
  commit-time lifecycle consistency enforcement
- Named CHECK constraints for status values, text lengths, date boundaries,
  correction numbering, actor, and archive reason on all four tables
- UNIQUE constraints: at most one Draft per Decision, at most one Confirmed
  snapshot per Decision, per-Decision sequential correction numbering
- FK constraints with ON DELETE RESTRICT/NO ACTION for snapshot and correction
  references; ON DELETE CASCADE for Draft-to-Decision enabling atomic discard
- Deferred CONSTRAINT TRIGGER on decisions for cross-table draft/snapshot
  consistency verification at commit time
- SQLAlchemy ORM models aligned with the migration: Decision, DecisionDraft,
  DecisionConfirmedSnapshot, DecisionCorrection
- Comprehensive real-PostgreSQL test suite (60 tests) covering migration
  lifecycle, schema inspection, data model constraints, lifecycle transitions,
  discard foundation, snapshot immutability, correction behavior, and trigger
  inspection
- ADR 0005 documenting the Decision Journal persistence and immutability
  foundation

### Boundaries

- Slice 3A adds no Decision service, repository workflow, API endpoint,
  Pydantic contract, router, or frontend `/decisions` page.
- No AuditEvent business write workflow, Redis logic, authentication,
  multi-user, multi-household, recommendation, Guardian, AI, Broker, trading,
  actual holdings, accounts, or monetary data is included.
- Slice 3B (Decision Backend Workflow and API): Not Authorized, Not Started.
- Slice 3C (Decision Frontend Workflow): Not Authorized, Not Started.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C remain Done.
- Slice 3 Technical Design Gate: Done.
- Slice 3A Decision Journal Persistence and Immutability Foundation: Done.
- Independent review: initial REQUEST CHANGES (1 BLOCKER), final APPROVE WITH
  NON-BLOCKING FOLLOW-UP. BLOCKER B1 (deferred trigger coverage gap) resolved
  with three cross-table deferred CONSTRAINT TRIGGERs and four bypass regression
  tests. 138 required PostgreSQL tests passed, 0 skipped.
- PR #11 approved for merge.
- Slice 3B and Slice 3C: Not Authorized, Not Started.

### Review Summary

- Initial independent review: REQUEST CHANGES with one BLOCKER finding.
- B1 resolved: deferred trigger coverage gap — original trigger fires only on
  decisions INSERT, missing UPDATE and child-table mutations that can bypass
  lifecycle consistency checks. Fixed by adding deferred CONSTRAINT TRIGGERs on
  decision_drafts (AFTER INSERT OR DELETE) and decision_confirmed_snapshots
  (AFTER INSERT OR DELETE), expanding decisions trigger to INSERT OR UPDATE, and
  updating the shared function to extract decision_id from TG_TABLE_NAME and
  query current database state at COMMIT time instead of relying on stale NEW
  records.
- Four bypass regression tests added: cross-transaction UPDATE to confirmed
  without snapshot, Draft deletion leaving orphan identity, snapshot insertion
  with retained Draft, and confirmed-to-draft status regression.
- Final independent review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP.
- All BLOCKER, HIGH, and MEDIUM findings resolved. Zero outstanding issues.
- Real PostgreSQL test suite: 138 passed, 43 deselected, 0 skipped, 20 warnings.
- Frontend test suite: 4 files, 62 tests passed (no regressions).

## [Unreleased] - Sprint 002 Slice 3 Technical Design Gate Complete

### Added

- Decision Journal Technical Design document covering Approach C (Stable
  Decision Identity + Draft + Immutable Confirmed Snapshot + Append-Only
  Correction) for the Decision Journal data model
- Fifteen Owner Decisions (OD-S3-1 through OD-S3-15) all Resolved by Project
  Owner — 2026-07-16, covering: multiple independent Drafts, Confirm required
  fields (mechanical validation only), no classification/tags, DATE type with
  future decision_date forbidden, current Published Policy Version reference
  only, 13-step Confirm transaction consuming Draft, Archive/unarchive
  lifecycle, full replacement Correction snapshots, correctable field set,
  Decision-filtered audit with Household timeline inclusion, provisional
  non-advisory UI copy, 3A/3B/3C implementation split, atomic never-Confirmed
  Draft discard with identity deletion, per-Decision sequential Correction
  numbering via MAX+1, and Archived Decision Correction eligibility
- Key design boundaries: Policy → Decision → Draft lock order, immutable
  Confirmed snapshot, atomic never-confirmed Draft discard, full replacement
  Corrections, per-Decision Correction numbering, Archive/unarchive,
  Archived Correction eligibility, Decision-filtered audit, Household
  timeline inclusion
- Seven AuditEvent action names following the existing Policy audit pattern:
  `decision.draft.created`, `decision.draft.updated`,
  `decision.draft.discarded`, `decision.confirmed`, `decision.archived`,
  `decision.unarchived`, `decision.correction.appended`
- Cursor-based Decision audit pagination: `before_sequence_number`, default 50,
  max 100, DB DESC / API ASC

### Boundaries

- No schema, migration, backend, API, frontend, or tests implementation is
  included. This is a design-only document.
- Merging the Technical Design does not authorize Slice 3 implementation.
- Slice 3A (Decision Persistence and Immutability): Not Started.
- Slice 3B (Decision Backend Workflow and API): Not Started.
- Slice 3C (Decision Frontend Workflow): Not Started.
- The Decision Journal records only what the user types, confirms, archives,
  and corrects. No recommendation, evaluation, scoring, suitability, AI,
  Guardian, Broker, market data, actual holdings, or trading behavior.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C remain Done.
- Slice 3 Technical Design Gate: Done.
- Independent review passed through four stages: initial REQUEST CHANGES
  (5 MEDIUM, 3 LOW), incremental APPROVE WITH NON-BLOCKING FOLLOW-UP,
  consistency review APPROVE WITH ONE MEDIUM FINDING, final focused APPROVE.
- All review findings resolved. Zero outstanding issues.
- PR #10 approved for merge.

## [Unreleased] - Sprint 002 Slice 2C Complete

### Added

- Local-only `/policy` workflow covering initial loading, missing Household,
  empty Policy, Draft editing, publication review, immutable Published Version,
  version history, Policy audit, and confirmed Draft discard states
- Typed browser API client for the approved Policy backend contracts with distinct
  404, 409, and 422 handling, abortable reads, and no mutation retries
- Explicit Draft text and whole-allocation saves with optimistic revisions,
  client-side semantic no-op detection, and local edit preservation on failures
- Exact target-allocation display totals calculated from decimal strings as integer
  hundredths without binary floating-point arithmetic or silent rounding
- Accessible mechanical publication checks and explicit confirmation using the
  approved non-advisory and local-only boundary
- Frontend component and API-client coverage for state transitions, conflicts,
  decimal handling, immutable history, audit recovery, safety copy, and request cleanup
- Independent core, Version-history, and Policy-audit resource states so auxiliary
  read failures cannot hide a successfully loaded Draft or Published Version
- Workspace-level semantic dirty tracking that blocks publication of a stale saved
  snapshot and requires explicit confirmation before reload discards local edits
- Generation- and AbortController-guarded audit/history reads, including guarded
  cursor merges, stable Version identity deduplication, and stale-result rejection
- Case-preserving allocation display-name comparison, Unicode code-point length
  validation, and row-specific accessible allocation action names
- Safe distinction between connection failures and unexpected HTTP server errors,
  without displaying response bodies or request payloads
- A compact immutable current Published Version summary when a Draft is also open

### Boundaries

- Slice 2C records and displays only user-entered Policy information; it does not
  evaluate suitability or provide advice, recommendations, trade instructions,
  scores, eligibility, rebalancing, or automated decisions.
- No backend behavior, migration, Python or frontend dependency, Compose, CI,
  authentication, Decision Journal, Guardian, AI, Broker, market, holding, or
  trading behavior is added.
- Full Docker runtime and end-to-end browser-path validation remain pending.
- Slice 3 remains unauthorized and Not Started.

### Status

- Slice 2A and Slice 2B remain Done.
- Slice 2C passed independent incremental review with conclusion APPROVE. All
  ten findings from the initial review (M-1 through M-4, L-1 through L-6) are
  fully resolved with zero new findings.
- PR #9 approved for merge.
- Sprint 002 remains In Progress. Slice 3 remains unauthorized and Not Started.

### Review Summary

- Initial independent review: REQUEST CHANGES (M-1 through M-4, L-1 through L-6).
- M-1 resolved: independent core/history/audit resource states prevent auxiliary
  failures from hiding a usable workspace.
- M-2 resolved: workspace-level semantic dirty tracking blocks publication of
  stale saved snapshots and requires explicit confirmation before reload.
- M-3 resolved: unified reload confirmation protects both editors from silent
  data loss; failed reloads preserve local edits.
- M-4 resolved: generation-guarded and AbortController-coordinated audit reads
  prevent stale responses from overwriting newer state.
- L-1 resolved: generation- and cursor-guarded history pagination with stable
  Version identity deduplication.
- L-2 resolved: case-preserving allocation display-name comparison matching
  backend NFKC + trim + whitespace collapse semantics.
- L-3 resolved: Unicode code-point length validation replacing HTML maxLength,
  with 200 emoji boundary tests.
- L-4 resolved: distinct PolicyNetworkError and PolicyApiError classes with
  neutral messages that never echo response bodies.
- L-5 resolved: CurrentPublishedSummary component renders immutable Published
  context alongside an editable Draft.
- L-6 resolved: row-specific accessible aria-labels for all allocation row
  controls with name-aware fallbacks.
- Frontend test suite: 4 files, 62 tests (up from 37), including deferred-promise
  race condition tests, dirty-state transition tests, Unicode boundary tests,
  error classification tests, and accessibility tests.

## [Unreleased] - Sprint 002 Slice 2B Complete

### Added

- Strict Pydantic contracts for ten Policy text fields and decimal-string target
  allocation values
- Policy, Draft, allocation, publication, immutable Version, history, and audit APIs
- Unicode NFKC/casefold allocation-name normalization and atomic whole-collection saves
- Synchronous service transactions with Policy-then-Draft locking, optimistic
  Draft revisions, named-conflict mapping, and atomic non-sensitive AuditEvents
- Real PostgreSQL API, rollback, immutable publication, concurrency, and race tests
- ADR 0004 documenting the Policy backend transaction and API boundary
- Transaction-scoped PATCH response snapshots that perform no Draft/allocation
  read after commit
- Optional empty-object validation for Policy creation requests: omitted bodies and
  `{}` are accepted, while non-empty objects, scalars, and arrays are rejected
- Expanded required PostgreSQL coverage for lifecycle races, replacement and
  allocation rollback, unrelated integrity failures, audit windows, text
  boundaries, and exact publication totals

### Boundaries

- Slice 2B provides a backend API only; no `/policy` frontend or frontend API
  client is included.
- Explicit JSON `null` is still accepted by `POST /api/policies` as the optional
  empty request; distinguishing it from an omitted body remains a LOW,
  non-blocking follow-up.
- The API records user-entered text and target percentages without evaluation,
  recommendation, scoring, eligibility, Guardian, AI, Broker, or trading behavior.
- Slice 2C and Slice 3 remain unauthorized and Not Started.

### Status

- Sprint 002 remains In Progress.
- Slice 2A remains Done.
- Slice 2B is complete and is not a production-readiness claim.
- Independent review initially concluded REQUEST CHANGES for M-1, M-2, and L-1.
  M-1 was resolved with an atomic transaction-scoped PATCH response snapshot,
  and M-2 was resolved with the required transaction, concurrency, rollback,
  audit-window, text-boundary, and exact-total coverage.
- Final independent incremental review conclusion: APPROVE WITH NON-BLOCKING
  FOLLOW-UP. Pull request #8 is approved for merge.
- L-1 remains partially resolved only for explicit JSON `null`, as disclosed
  above; it does not block Slice 2B completion.
- The Policy frontend and complete Policy user experience remain unimplemented.
- Full Docker/browser runtime validation and the Alembic `path_separator = os`
  warning remain non-blocking Backlog items.

## [Unreleased] - Sprint 002 Slice 2A Complete

### Added

- Alembic revision `0002_investment_policy_foundation`
- Five approved Investment Policy, Draft, allocation, and Version persistence tables
- Database-generated unique AuditEvent insertion sequence with preserved Slice 1 data
- Named Policy cardinality, version, allocation, normalization, and range constraints
- PostgreSQL immutable Version and Version-allocation trigger functions
- Deferred commit-time sealing enforcement
- SQLAlchemy mappings aligned with the migration
- Real PostgreSQL tests for fresh and incremental migration, downgrade/re-upgrade,
  constraints, triggers, rollback, and insertion sequencing
- ADR 0003 documenting immutable Policy snapshot persistence

### Boundaries

- Slice 2A adds no Policy repository workflow, service, API endpoint, Pydantic
  Policy contract, or frontend `/policy` experience.
- No recommendation, Guardian, AI, Broker, trading, authentication, Slice 2B,
  Slice 2C, or Slice 3 behavior is included.
- AuditEvent sequence values provide deterministic database insertion order, not
  concurrent transaction commit order, and may contain rollback gaps.

### Status

- Sprint 002 remains In Progress.
- Slice 2A passed independent review with conclusion APPROVE WITH NON-BLOCKING
  FOLLOW-UP and pull request #7 is approved for merge.
- Slice 2A completes only the Investment Policy persistence and immutability
  foundation; it is not a production-readiness claim.
- Slice 2B, Slice 2C, and Slice 3 remain unauthorized.
- Docker runtime/browser validation and full AuditEvent pagination remain Backlog items.

### Non-blocking follow-ups

- Strengthen schema/trigger regression assertions for all allocation unique
  constraints and index predicates, combined seal-plus-content mutation, repeated
  Superseded mutation, and multi-row forbidden statements.
- In a separate maintenance change, add Alembic `path_separator = os` and rerun
  offline and real PostgreSQL migration validation.

## [Unreleased] - Sprint 002 Slice 1 Complete

### Added

- PostgreSQL-backed sole HouseholdProfile create, current-read, and update APIs
- Atomic append-only AuditEvent creation and read-only timeline API
- Explicit Alembic migration for `household_profiles` and `audit_events`
- Local-only Household page with create, summary, edit, validation, error, and audit states
- Real PostgreSQL CI service, migration, singleton, and transaction rollback checks
- A project-specific CI gate that fails if required real PostgreSQL tests cannot run
- Named PostgreSQL checks mirroring every approved HouseholdProfile field limit
- Independent audit loading/error state and GET-only retry after a successful mutation
- ADR 0002 for synchronous PostgreSQL persistence and transaction boundaries

### Boundaries

- All host ports default to `127.0.0.1`; no authentication or public deployment
- No Policy, Allocation, Journal, AI, Guardian, Broker, recommendation, trading,
  actual holdings, accounts, or monetary data
- Sprint 002 is not complete, and Slice 2 is not authorized

### Validation Status

- Local Ruff, backend tests available without PostgreSQL, frontend lint,
  type-check, tests, production build, dependency audit, Alembic offline SQL,
  YAML parsing, localhost binding inspection, and secret scan pass
- Real PostgreSQL and Compose checks run in GitHub CI
- Local test runs may skip PostgreSQL-marked tests when `TEST_DATABASE_URL` is not
  configured; the explicit CI-required mode fails instead of skipping
- Independent review initially concluded REQUEST CHANGES; the PostgreSQL CI gate,
  database constraints, and audit refresh UX findings were resolved
- Final independent review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP
- Docker CLI is unavailable in the local implementation environment, so full
  Docker runtime and browser-path verification remains pending

### Non-blocking Follow-ups

- Complete full Docker runtime and browser-path validation
- Align `NEXT_PUBLIC_API_URL` with Docker's build-time public environment behavior
- Split Python runtime and development dependencies before production hardening
- Design AuditEvent pagination before higher-volume event sources are introduced

### Status

- Sprint 002 Slice 1 is complete and approved for merge.
- This completes one implementation slice, not Sprint 002 as a whole.
- Sprint 002 remains In Progress; Slice 2 is not authorized and Not Started.
- This local-only foundation is not a production-readiness claim or product release.

## [Unreleased] - Sprint 001 Complete

### Added

- Frontend health endpoint test using the Node.js test runner
- CI execution of the frontend health test
- CI validation of the Docker Compose configuration
- Dockerfiles for the existing `frontend/` and `apps/api/` applications
- `compose.yaml` for the web, API, PostgreSQL, and Redis local stack
- Docker build-context ignore files

### Validation

- Frontend lint, type-check, health test, production build, and production
  dependency audit pass locally
- Backend Ruff and pytest checks pass locally
- Compose YAML, CI YAML, build contexts, dependency paths, and container commands
  pass static consistency checks
- Docker runtime verification was not completed because Docker is unavailable in
  the current environment

### Status

- Sprint 001: Done and approved for merge after independent code review
- Review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP
- Docker runtime verification remains an explicitly disclosed non-blocking
  follow-up
- Sprint 002: Not Started
- This entry records foundation completion and is not a product feature release

## [0.1.1] - 2026-07-12

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
- Finalized Sprint 001 and Sprint 001.1 through pull request #1
- Squash-merged the reviewed foundation into `main` as
  `b3801c64fa09856d491317b0ebda45007c210ae0`
- Confirmed GitHub Actions backend and frontend checks pass for push and pull
  request events

### Status

- Sprint 001: Done
- Sprint 001.1: Done
- Sprint 002: Not Started

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
