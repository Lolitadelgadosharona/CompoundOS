# Sprint 020 — Design Direction
# Production Hardening & Real Usage

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 019: COMPLETE
> Sprint 020: DESIGN ONLY

---

## Objective

After ten sprints of capability building (012-019), Sprint 020
shifts from feature development to production quality. The system
works. Now make it reliable, secure, and genuinely usable by the
Owner on a daily basis.

---

## Slice A — Security Hardening

### Goal
Ensure CompoundOS is safe to deploy with real financial data.

### Tasks
- Dependency audit (pip-audit, safety)
- Environment variable hardening (no defaults, no example .env)
- SQL injection review (all queries use parameterized binds)
- CORS configuration audit
- Rate limiting on API endpoints
- Session/API key rotation guidance
- Security documentation for deployment

### Deliverable
Security audit report + remediation

---

## Slice B — Data Reliability

### Goal
Make the data pipeline resilient to real-world failures.

### Tasks
- Alpha Vantage error handling audit (rate limits, API changes)
- Cache warming for commonly-researched symbols
- Database connection pooling configuration
- Migration integrity verification (all CHECKs validated)
- Data validation on pipeline inputs/outputs
- Graceful degradation testing (simulate provider failures)

### Deliverable
Data reliability test suite + monitoring

---

## Slice C — AI Quality Calibration

### Goal
Ensure AI outputs are consistently useful, not just technically
correct.

### Tasks
- Prompt engineering review across all 6 perspectives
- Response quality consistency check (10 runs on AAPL)
- Hallucination detection (cited facts vs. LLM-invented facts)
- Confidence score calibration (compare predicted vs. actual)
- Output length and structure consistency
- Multi-model comparison (Claude vs. GPT-4o output quality)

### Deliverable
AI quality report with prompt tuning recommendations

---

## Slice D — Owner Experience

### Goal
Make the daily dashboard genuinely pleasant to use.

### Tasks
- Dashboard performance optimization (lazy loading, caching)
- Mobile-responsive layout testing
- Accessibility audit (contrast, keyboard navigation)
- Loading states and error messages (never show raw tracebacks)
- Search and filter for research history
- Keyboard shortcuts for common actions
- Dark/light theme toggle

### Deliverable
UX polish pass + performance benchmarks

---

## Constraints

- No broker integration
- No trading
- No autonomous investment execution
- AI advisory only
- Owner remains final authority
- All LLM calls through GovernedLLMExecutor

---

## Owner Decisions Required

6-8 decisions covering:
- Deployment timeline (when to go live on VPS?)
- API service tier (Alpha Vantage free vs. premium)
- Which model to use as primary (Claude vs. GPT-4o)
- Security requirements for production
- Backup frequency and retention policy
- Monitoring and alerting preferences
