# Sprint 020 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 019: COMPLETE
> Sprint 020: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Security Hardening

### OD-20-1 — Audit Scope

**Question:** What should the security audit cover?

**Scope (recommended):**
- Dependency vulnerability scan (pip-audit, safety)
- SQL injection review (verify all queries use parameterized binds)
- Environment variable audit (no defaults, no example .env with secrets)
- CORS configuration for production deployment
- API key rotation mechanism
- Error message sanitization (no stack traces in responses)

**Recommendation:** Full scope. These are table stakes for any system
handling financial data.

---

### OD-20-2 — Rate Limiting

**Question:** Should API rate limiting be implemented?

**Options:**
- A) Yes — 100 req/min for API, 1000 req/min for dashboard
- B) No — solo-Owner use case doesn't need rate limiting
- C) Per-endpoint limits (research endpoints stricter)

**Recommendation:** **A — Moderate defaults.** 100 req/min for API
endpoints prevents accidental abuse and protects the Alpha Vantage
free tier. Dashboard can be more generous since it serves one user.

---

### OD-20-3 — Access Control

**Question:** How should API access be controlled in production?

**Current:** X-API-Key middleware (Sprint 010-D).

**Production additions (recommended):**
- Environment check (ENVIRONMENT=production requires valid API key)
- Key rotation: document how to generate and deploy new keys
- No default keys — fail closed on missing config
- Rate limit per API key

---

## Slice B — Data Reliability

### OD-20-4 — Provider Failure Strategy

**Question:** What happens when Alpha Vantage returns errors?

**Graceful degradation (already implemented in Sprint 013-B):**
- Rate limit → retry with backoff
- Timeout → mark as stale, use last good cache
- Malformed response → flag data quality, reduce confidence
- Complete failure → missing_sources, no fabrication

**Recommendation:** **Keep existing strategy** — it's proven.
Sprint 020 should audit and harden, not redesign.

---

### OD-20-5 — Cache Strategy

**Question:** Should we pre-warm caches for commonly-researched symbols?

**Options:**
- A) Yes — warm cache for AAPL, MSFT, GOOGL, BRK.B, JNJ on startup
- B) No — cache-populates on first research request
- C) Scheduled cache refresh (daily at market open)

**Recommendation:** **B — Cache on first request.** Pre-warming adds
complexity without proportional value. Cache TTLs are already short
(6h for prices). Owner's first research of the day populates cache
naturally.

---

## Slice C — AI Quality Calibration

### OD-20-6 — Hallucination Prevention

**Question:** How should the system detect and prevent AI hallucination?

**Defense layers (recommended):**
- System prompt explicitly instructs: "Only cite facts from provided
  evidence. If uncertain, state uncertainty."
- ResponseValidator enforces: all citations must reference evidence
  bundle sources
- Post-generation check: flag claims without backing evidence
- Display: hallucinated claims marked as "unverified"

**Gate:** Memo with >3 unverified claims gets quality score penalty.
Owner sees the flag; AI doesn't suppress the memo.

---

### OD-20-7 — Confidence Calibration

**Question:** How should AI confidence be calibrated?

**Method:**
- Run 5 research cycles on AAPL with different prompt seeds
- Compare predicted confidence vs. variation in output
- If confidence varies >20 points across runs, flag as "inconsistent"
- Target: consistent confidence scores (±10 points) for the same
  factual input

**Metric:** Confidence standard deviation across runs should be ≤15.

---

## Slice D — Owner Experience

### OD-20-8 — Dashboard Priorities

**Question:** What UX improvements deliver the most value?

**Priority order (recommended):**
1. Loading states — show spinners, never blank pages
2. Error messages — human-readable, never tracebacks
3. Mobile-responsive — dashboard usable on phone/tablet
4. Search/filter — research history searchable by symbol
5. Dark/light theme — respect OS preference
6. Keyboard shortcuts — `r` for research, `d` for decisions

**Deferred:** Real-time updates, WebSocket push, animations.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-20-1 | A | Audit scope | Full: deps, SQL injection, env vars, CORS, keys |
| OD-20-2 | A | Rate limiting | 100 req/min API, generous dashboard |
| OD-20-3 | A | Access control | X-API-Key hardening, no defaults |
| OD-20-4 | B | Provider failures | Keep Sprint 013-B strategy, audit and harden |
| OD-20-5 | B | Cache strategy | Populate on first request |
| OD-20-6 | C | Hallucination | 3-layer defense, flag unverified claims |
| OD-20-7 | C | Confidence calibration | 5-run consistency check, target ±10 |
| OD-20-8 | D | UX priorities | Loading, errors, mobile, search, theme, shortcuts |

---

## Architecture Preservation

All Sprint 012-019 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
