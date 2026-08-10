# Sprint 013 — Owner Decisions

> **STATUS: OWNER DECISIONS DOCUMENTED — PENDING APPROVAL**
>
> Sprint 012: COMPLETE (all 4 slices done)
> Sprint 013: DESIGN COMPLETE — AWAITING OWNER APPROVAL
>
> 8 decisions documented. Final version: `SPRINT_013_OWNER_DECISIONS_FINAL.md`

---

## OD-13-1: LLM Provider Selection

### Question
Which LLM providers should be connected first?

### Options

| Option | Providers | Cost/Run |
|---|---|---|
| A: Single provider (Claude only) | Anthropic Claude for all 7 calls | ~$0.04 |
| B: Multi-provider (Claude + GPT-4o + Gemini) | Best model per perspective (as designed) | ~$0.06 |
| C: Open-source only (no API keys) | Local ollama/Llama models | $0 (hardware cost) |

### Recommendation
**Option B — Multi-provider.** Different models have different strengths:
Claude for structured financial analysis, GPT-4o for broad synthesis,
Gemini for long-context memo generation. For ~$0.06/research run,
the quality improvement justifies the marginal cost increase.

### Owner Decision
- [ ] APPROVE — Option A (Claude only)
- [ ] APPROVE — Option B (Multi-provider — recommended)
- [ ] APPROVE — Option C (Open-source only)
- [ ] OTHER: _______________

---

## OD-13-2: Market Data Provider Selection

### Question
Which market data provider should be used?

### Options

| Option | Provider | Cost | Rate Limit |
|---|---|---|---|
| A: Alpha Vantage free tier | Alpha Vantage | Free | 25 req/day |
| B: Alpha Vantage premium | Alpha Vantage ($50/mo) | $50/mo | 75 req/min |
| C: Yahoo Finance (unofficial) | yfinance library | Free | No formal limit |

### Recommendation
**Option A — Alpha Vantage free tier.** 25 requests/day supports ~4
research runs/day. Sufficient for V1 single-owner usage. Upgrade to
premium when volume exceeds free tier. Yahoo Finance (Option C)
avoids API key management but has no SLA and may break without notice.

### Owner Decision
- [ ] APPROVE — Option A (Alpha Vantage free — recommended)
- [ ] APPROVE — Option B (Alpha Vantage premium)
- [ ] APPROVE — Option C (Yahoo Finance unofficial)
- [ ] OTHER: _______________

---

## OD-13-3: API Key Management

### Question
How should provider API keys be managed?

### Options

| Option | Description |
|---|---|
| A: Environment variables only | Keys in `.env` file, never in database. Loaded at startup. |
| B: Encrypted key store | Keys stored encrypted in database with master key in env. Rotatable without restart. |
| C: External secrets manager | AWS Secrets Manager / HashiCorp Vault. Enterprise-grade. |

### Recommendation
**Option A — Environment variables only.** For V1 single-owner system,
`.env` is sufficient. Keys are never in code, never in database, never
in logs. Option B adds complexity without proportional benefit for
one user. Option C is for multi-user/commercial deployments.

### Owner Decision
- [ ] APPROVE — Option A (Environment variables — recommended)
- [ ] APPROVE — Option B (Encrypted key store)
- [ ] APPROVE — Option C (External secrets manager)
- [ ] OTHER: _______________

---

## OD-13-4: Data Freshness Rules

### Question
When should cached market data be considered stale?

### Options

| Option | Price | Fundamentals | Company Profile |
|---|---|---|---|
| A: Aggressive | 1 hour | 7 days | 24 hours |
| B: Moderate | 6 hours | 30 days | 7 days |
| C: Conservative | 24 hours | 90 days | 30 days |

### Recommendation
**Option B — Moderate.** Aligned with OD-12-C-3 (already approved).
6-hour price data + 30-day fundamentals + 7-day profiles. Sufficient
for family office making occasional decisions, not daily trading.

### Owner Decision
- [ ] APPROVE — Option A (Aggressive)
- [ ] APPROVE — Option B (Moderate — recommended)
- [ ] APPROVE — Option C (Conservative)
- [ ] OTHER: _______________

---

## OD-13-5: Cost Limits

### Question
What LLM cost limits should be enforced?

### Options

| Option | Per Run | Per Day | Per Month |
|---|---|---|---|
| A: No limits | Unlimited | Unlimited | Unlimited |
| B: Soft limits (log + alert) | $0.25 | $2.00 | $30.00 |
| C: Hard limits (block) | $0.25 | $2.00 | $30.00 |

### Recommendation
**Option B — Soft limits (log + alert).** Log-only for V1 (OD-12-D-3
already approved). Add notification_event alerts when thresholds are
exceeded. Don't block research — this is a research tool for the Owner.
Hard limits risk blocking legitimate analysis.

### Owner Decision
- [ ] APPROVE — Option A (No limits)
- [ ] APPROVE — Option B (Soft limits: log + alert — recommended)
- [ ] APPROVE — Option C (Hard limits: block)
- [ ] OTHER: _______________

---

## OD-13-6: Citation Requirements

### Question
Should AI-generated memos require citations to evidence sources?

### Options

| Option | Description |
|---|---|
| A: No citations | Memo contains analysis without source traceability |
| B: Inline citations | Every claim cites [source: data_type, period]. Linked to committee_evidence_items. |
| C: Full reference section | Memo has a "Sources" section listing all evidence. Inline citations optional. |

### Recommendation
**Option B — Inline citations.** Citations provide audit traceability
from memo claim → evidence item → provider response. Essential for
Owner trust: "Where did the AI get this number?" The answer must be
one query away.

### Owner Decision
- [ ] APPROVE — Option A (No citations)
- [ ] APPROVE — Option B (Inline citations — recommended)
- [ ] APPROVE — Option C (Full reference section)
- [ ] OTHER: _______________

---

## OD-13-7: Human Approval Boundary

### Question
Where must AI stop and Owner approve?

### Options

| Option | AI Auto | Owner Required |
|---|---|---|
| A: Full auto | Research → Memo → Recommendation → Decision | Nothing (Owner reviews post-hoc) |
| B: Advisory only | Research → Memo → Recommendation | Decision approval |
| C: Research only | Research → Memo | Recommendation + Decision approval |

### Recommendation
**Option B — Advisory only.** AI produces: research data, perspective
analyses, investment memo, confidence score, and a recommendation
(BUY/HOLD/PASS). The Owner receives the complete analysis and makes
the final decision. This is the model defined since Sprint 009 and
enforced by PermissionGate (Sprint 012-D).

### Owner Decision
- [ ] APPROVE — Option A (Full auto — AI decides)
- [ ] APPROVE — Option B (Advisory only — recommended)
- [ ] APPROVE — Option C (Research only — AI makes no recommendation)
- [ ] OTHER: _______________

---

## OD-13-8: Provider Failure Handling

### Question
What happens if Alpha Vantage or an LLM provider is unavailable?

### Options

| Option | External Data Down | LLM Provider Down |
|---|---|---|
| A: Fail the entire run | Run fails | Run fails |
| B: Graceful degradation | Continue with internal data; flag missing | Try fallback model; if all fail, fail the run |
| C: Queue and retry | Retry with backoff indefinitely | Retry with backoff indefinitely |

### Recommendation
**Option B — Graceful degradation.** For market data: internal portfolio,
policy, guardian, and knowledge memory data is always available. For
LLM: if one provider is down, attempt fallback. If claude-sonnet-4
fails, try gpt-4o for Value/Growth/Risk. If all LLM providers fail,
mark the run failed. Never fabricate data.

### Owner Decision
- [ ] APPROVE — Option A (Fail entire run)
- [ ] APPROVE — Option B (Graceful degradation — recommended)
- [ ] APPROVE — Option C (Queue and retry)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

All decisions preserve:

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes + recommends; Owner decides (OD-13-7) |
| No automatic investment | Investment approval requires Owner action |
| No trading | No trade code paths |
| No broker integration | No broker interfaces |
| No credentials in code | Environment variables only (OD-13-3) |
| No fabricated data | Missing data → flagged, not guessed (OD-13-8) |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-13-1 | LLM provider selection | Multi-provider: Claude + GPT-4o + Gemini (B) |
| OD-13-2 | Market data provider | Alpha Vantage free tier (A) |
| OD-13-3 | API key management | Environment variables only (A) |
| OD-13-4 | Data freshness | Moderate: 6h/30d/7d (B) |
| OD-13-5 | Cost limits | Soft limits: log + alert (B) |
| OD-13-6 | Citation requirements | Inline citations to evidence sources (B) |
| OD-13-7 | Human approval boundary | Advisory only: AI recommends, Owner decides (B) |
| OD-13-8 | Provider failure handling | Graceful degradation (B) |
