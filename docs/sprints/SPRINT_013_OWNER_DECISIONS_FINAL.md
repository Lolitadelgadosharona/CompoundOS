# Sprint 013 — Owner Decisions (Final)

> **STATUS: OWNER DECISIONS DOCUMENTED — PENDING APPROVAL**
>
> Sprint 012: COMPLETE
> Sprint 013: DESIGN COMPLETE — AWAITING OWNER DECISIONS
>
> 8 decisions documented for Owner review. All preserve: AI advisory only,
> no trading, no broker integration, no credentials in code.

---

## OD-13-1: LLM Provider Strategy

### Question
Which LLM providers and routing rules should be configured?

### Recommendation

**Multi-provider with per-perspective routing:**

| Perspective | Provider | Model | Rationale |
|---|---|---|---|
| Value | Anthropic | claude-sonnet-4 | Structured financial reasoning |
| Growth | Anthropic | claude-sonnet-4 | Same model for paired Value/Growth |
| Risk | Anthropic | claude-sonnet-4 | Risk analysis benefits from structure |
| Macro | OpenAI | gpt-4o | Broad economic synthesis |
| Policy | Anthropic | claude-sonnet-4 | Rule alignment checking |
| Portfolio Fit | OpenAI | gpt-4o | Numerical allocation reasoning |
| Synthesis/Memo | Google | gemini-2.5-pro | Long-context document synthesis |

**Routing**: Configured via `prompt_templates.default_model`. Not hardcoded.
Changing models = new active prompt version.

### Owner Decision
- [ ] APPROVE — Multi-provider routing as documented above
- [ ] MODIFY — (specify changes): _______________

---

## OD-13-2: Credential Management

### Question
How are provider API keys managed now and in the future?

### Recommendation

**V1: Environment variables only.**
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AV_API_KEY`
- Loaded at provider init via `os.environ.get()`
- Never stored in database
- Never logged or included in API responses
- `.env` file for local development (in `.gitignore`)

**Future path**: When multi-user support arrives (Sprint 020+), migrate to
encrypted key store with per-household provider credentials. No migration
needed now.

### Owner Decision
- [ ] APPROVE — V1: Environment variables only; future: encrypted store
- [ ] MODIFY — (specify): _______________

---

## OD-13-3: Market Data Provider

### Question
Which market data source for V1, and what's the upgrade path?

### Recommendation

**V1: Alpha Vantage free tier.**
- 25 requests/day (~4 research runs/day)
- Covers: overview, income statement, balance sheet, cash flow, price history
- Free, no credit card required
- Provenance: `source="alpha_vantage"`, full ProvenanceEnvelope

**Future**: Provider abstraction (already defined in Sprint 012-C) allows
adding Bloomberg, Refinitiv, or premium Alpha Vantage without changing
the pipeline. Just implement another `MarketDataProvider`.

### Owner Decision
- [ ] APPROVE — Alpha Vantage free tier V1; pluggable providers future
- [ ] MODIFY — (specify): _______________

---

## OD-13-4: Data Freshness Rules

### Question
What TTL makes market data stale?

### Recommendation

| Data Type | TTL | Rationale |
|---|---|---|
| Price history | 6 hours | Intraday decisions need recent quotes |
| Company overview | 7 days | Descriptions/classifications change rarely |
| Income statement | 90 days | Quarterly filing cadence |
| Balance sheet | 90 days | Same quarterly schedule |
| Cash flow | 90 days | Same quarterly schedule |
| News | 24 hours | Time-sensitive but not real-time |
| SEC filings | Until next filing | Event-driven, not time-driven |

Cached data with TTL expired → `data_quality_status = STALE`.
Pipeline may use stale data with reduced confidence. Never fabricate.

### Owner Decision
- [ ] APPROVE — Freshness rules as documented above
- [ ] MODIFY — (specify): _______________

---

## OD-13-5: Research Cost Governance

### Question
What LLM cost limits and tracking should be enforced?

### Recommendation

**V1: Log-only tracking with soft thresholds.**

| Limit | Threshold | Action |
|---|---|---|
| Per run | $0.25 | Log only (no blocking) |
| Per day | $2.00 | Log + create notification_event |
| Per month | $30.00 | Log + create notification_event |

**Token limits per call:**

| Model | Max Input | Max Output |
|---|---|---|
| claude-sonnet-4 | 4,000 | 2,000 |
| gpt-4o | 4,000 | 2,000 |
| gemini-2.5-pro | 8,000 | 4,000 |

**Failure**: If a run exceeds per-run threshold, complete the run but
flag in `llm_execution_log`. No automatic blocking. Owner reviews
manually.

### Owner Decision
- [ ] APPROVE — V1: Log-only with soft thresholds as documented
- [ ] MODIFY — (specify): _______________

---

## OD-13-6: Citation Requirements

### Question
Must AI-generated research memo cite evidence sources?

### Recommendation

**Mandatory inline citations.** Every factual claim in the investment
memo MUST reference its evidence source:

```
✅ "Revenue grew 15% YoY to $383B" [source: income_statement, FY2025]
✅ "P/E ratio of 35x vs sector 22x" [source: overview, Alpha Vantage]
✅ "Positive cash flow of $100B" [source: cash_flow, FY2025]
❌ "The company is doing well"  (unsupported claim)
```

**Implementation**: LLM prompt instructs the model to produce citations.
Post-generation validation checks citation format. Missing citations
→ memo flagged, confidence reduced.

### Owner Decision
- [ ] APPROVE — Mandatory inline citations to evidence sources
- [ ] MODIFY — (specify): _______________

---

## OD-13-7: Human Approval Boundary

### Question
Where does AI stop and Owner authority begin?

### Recommendation

**AI may (automatically):**
1. Fetch market data from Alpha Vantage
2. Load portfolio/policy/guardian/knowledge data
3. Execute 6 LLM perspective analyses
4. Generate investment memo with citations
5. Calculate confidence score
6. Produce BUY/HOLD/PASS recommendation
7. Store results in database

**Owner must (explicit action required):**
1. Create investment idea (POST /api/ideas)
2. Request committee review
3. Start AI research (POST /api/research/start)
4. Review AI analysis in Dashboard
5. Approve or reject investment decision

**AI may NEVER:**
1. Create investment ideas on its own
2. Approve investments
3. Execute trades
4. Connect to brokers
5. Modify policy rules
6. Change prompt templates

This boundary is enforced by `PermissionGate` (Sprint 012-D).

### Owner Decision
- [ ] APPROVE — AI advisory only, Owner final authority, as documented
- [ ] MODIFY — (specify): _______________

---

## OD-13-8: Provider Failure Handling

### Question
What happens when Alpha Vantage or an LLM provider fails?

### Recommendation

| Failure | Strategy | Confidence Impact |
|---|---|---|
| Alpha Vantage down | Continue with internal data; log `missing_sources: [market_data]` | Reduce evidence_quality dimension ~50% |
| One LLM provider down | Fall back to another provider for that perspective | Minimal if fallback succeeds |
| All LLM providers down | Mark run `failed`; preserve partial evidence | Run fails |
| LLM response invalid | Retry once with corrected prompt | None if retry succeeds |
| Rate limit (429) | Respect Retry-After; max 3 retries | None |
| Auth failure (401/403) | Fail fast; do not retry | Perspective fails |

**Key principle**: Never fabricate data. Missing external data is
better than guessed data. The Owner can always re-run research when
the provider recovers.

### Owner Decision
- [ ] APPROVE — Graceful degradation with provider fallback as documented
- [ ] MODIFY — (specify): _______________

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-13-1 | LLM provider strategy | Multi-provider: Claude + GPT-4o + Gemini, per-perspective routing |
| OD-13-2 | Credential management | V1: Environment variables; future: encrypted store |
| OD-13-3 | Market data provider | Alpha Vantage free tier; future: pluggable providers |
| OD-13-4 | Data freshness | price=6h, overview=7d, financials=90d, news=24h |
| OD-13-5 | Cost governance | Log-only, thresholds at $0.25/run, $2/day, $30/mo |
| OD-13-6 | Citation requirements | Mandatory inline citations to evidence sources |
| OD-13-7 | Human approval boundary | AI recommends, Owner decides. Enforced by PermissionGate |
| OD-13-8 | Provider failure handling | Graceful degradation, provider fallback, no fabrication |
