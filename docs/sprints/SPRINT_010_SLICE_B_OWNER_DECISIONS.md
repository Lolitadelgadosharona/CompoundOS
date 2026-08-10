# Sprint 010 Slice B — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 010 Slice B Design: COMPLETE (08309ec)
> 4 decisions require Owner review before implementation begins.

---

## OD-10-B-1: Default Concentration Thresholds

### Question
What default thresholds should Guardian use for concentration checks when
no explicit `policy_rule` exists?

### Context
Sprint 010 Slice B adds three concentration check types. When the Owner has
not created matching `policy_rules`, Guardian uses fallback defaults. These
defaults determine alert sensitivity before the Owner customizes thresholds.

### Options

| Option | Single Position | Sector | Exploration | Pros | Cons |
|---|---|---|---|---|---|
| **A: Conservative** | 20% | 40% | 10% | Catches risk early; Owner can relax via policy | May produce false positives for concentrated portfolios |
| **B: Relaxed** | 30% | 50% | 15% | Less noise for concentrated strategies | May miss genuine risk |
| **C: No defaults** | N/A | N/A | N/A | Forces Owner to explicitly define risk tolerance | No protection until policy rules are created |

### Architecture Impact
- Option A/B: Default thresholds are hardcoded constants in guardian_intelligence.py. Owner can override at any time by creating `policy_rules` with matching `rule_type`.
- Option C: Checks without matching policy_rules return "skipped — no policy defined" instead of evaluating. Zero false positives, but zero protection until Owner acts.

### Recommendation
**Option A — Conservative (20%/40%/10%).** Guardian is a safety system.
Conservative defaults protect the portfolio immediately. The Owner can
relax thresholds by creating policy rules anytime. A false positive
(warning the Owner about a 22% position when the limit is 20%) is
preferable to a false negative (no alert for a 35% position).

### Owner Decision
- [ ] APPROVE — Option A (Conservative: 20%/40%/10%)
- [ ] APPROVE — Option B (Different thresholds: ___ / ___ / ___)
- [ ] APPROVE — Option C (No defaults, policy required)
- [ ] OTHER (specify): _______________

---

## OD-10-B-2: Critical Guardian BLOCK_RECOMMENDATION

### Question
When Guardian detects a **critical** event (e.g. exploration_capital_limit
exceeded), should Committee review requests be blocked?

### Context
The Committee bridge (Slice A) allows the Owner to request AI analysis of
investment ideas. A critical Guardian event indicates a safety rail violation.
The question is whether the system should prevent the Owner from requesting
new AI analysis while a critical risk is active.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Block all new reviews** | Committee bridge returns 409 Conflict while any critical Guardian event is unacknowledged | Safety-first; prevents analysis during active risk; Owner must acknowledge risk before proceeding | Adds friction; Owner may want analysis to help resolve the situation |
| **B: Block risk-increasing reviews** | Block only review requests for ideas that would increase the violated constraint (e.g. block new EXPLORATION ideas when exploration limit exceeded) | Targeted safety; allows analysis of mitigating ideas | Complex to implement; requires idea-to-constraint mapping |
| **C: Warning only** | Critical events generate notifications but never block workflow | No friction; Owner always in control | System safety rail is informational only; no enforcement |

### Architecture Impact
- Option A: Committee bridge checks for unacknowledged critical Guardian events before accepting review requests. Adds ~40 lines to committee_bridge router.
- Option B: Requires mapping each idea's proposed_allocation_pct and target bucket against active violations. ~150 lines, more complex testing.
- Option C: Zero code changes. Guardian events are notifications only.

### Recommendation
**Option A — Block all new reviews.** Critical Guardian events represent
safety rail violations. The Owner should acknowledge the risk before
proceeding with new analysis. This is not blocking the Owner — it's
requiring conscious acknowledgment. The Owner can still:
- Acknowledge the event (one click)
- Adjust the policy threshold
- Reduce the violating position
- Then proceed with review

The BLOCK_RECOMMENDATION is a speed bump, not a wall.

### Owner Decision
- [ ] APPROVE — Option A (Block all new Committee reviews)
- [ ] APPROVE — Option B (Block risk-increasing reviews only)
- [ ] APPROVE — Option C (Warning only, no blocking)
- [ ] OTHER (specify): _______________

---

## OD-10-B-3: Data Staleness Threshold

### Question
At what age should position data be flagged as "stale" by Guardian?

### Context
When the Owner imports portfolio data via CSV (Sprint 009-D), positions
carry `observed_at` timestamps. Guardian's `data_quality_staleness` check
flags positions where `observed_at` is older than the threshold. This
ensures the Owner knows when portfolio data may be outdated.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: 24 hours** | Flag positions with observed_at > 24 hours old | Prompt alert for daily-import workflow | Tight for occasional import users |
| **B: 48 hours** | Flag after 2 days | Tolerates weekend gaps; less noise | Risk of 2-day-old data going unnoticed |
| **C: Per-account configurable** | Each data source has its own staleness threshold in metadata | Flexible; fast sources get tight thresholds, manual sources get relaxed | More complex; requires metadata schema extension |

### Architecture Impact
- Option A/B: Single integer constant in guardian_intelligence.py
- Option C: Requires reading `data_sources.metadata` for threshold config;
  extends DataSource model; ~50 extra lines

### Recommendation
**Option A — 24 hours.** The Owner imports data manually. Daily import means
data is never more than 24 hours stale. A 24-hour threshold catches missed
imports promptly. If the import schedule is less frequent, the Owner can
adjust the check's `staleness_days` per check definition (existing field).

### Owner Decision
- [ ] APPROVE — Option A (24 hours)
- [ ] APPROVE — Option B (48 hours)
- [ ] APPROVE — Option C (Per-account configurable)
- [ ] OTHER (specify): _______________

---

## OD-10-B-4: Guardian Evaluation Schedule

### Question
How should Guardian evaluation runs be triggered?

### Context
Guardian currently supports scheduled evaluation via the Automation worker
(Sprint 005). Slice B does not change the scheduling mechanism, but the
Owner should decide the default cadence for the new checks.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Daily** | Guardian evaluates all checks once per day via Automation worker | Regular cadence; catches drift within 24h; low overhead | Misses intra-day risk if positions change rapidly |
| **B: Manual only** | Owner triggers evaluation via POST /api/guardian/evaluate | Full Owner control; no background processing | No automatic monitoring; risk of forgotten evaluations |
| **C: On-import trigger** | Guardian runs automatically after CSV import completes | Immediate feedback; data is always evaluated when fresh | Couples import and evaluation; increases import latency |

### Architecture Impact
- Option A: Automation worker job_definitions row for guardian_evaluation.
  Schedule: `0 6 * * *` (6 AM daily). Existing worker infrastructure (Sprint 005).
- Option B: No automation. API endpoint only. Manual trigger.
- Option C: Requires calling evaluate_core from import_service after successful
  import. Adds evaluation latency to import response.

### Recommendation
**Option A — Daily schedule + manual override.** Daily evaluation ensures
consistent monitoring without Owner intervention. The manual POST
/api/guardian/evaluate endpoint remains available for on-demand evaluation.
This gives both automatic safety and Owner control.

### Owner Decision
- [ ] APPROVE — Option A (Daily schedule + manual override)
- [ ] APPROVE — Option B (Manual only)
- [ ] APPROVE — Option C (On-import trigger)
- [ ] OTHER (specify): _______________

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-10-B-1 | Default thresholds | Conservative: 20%/40%/10% | |
| OD-10-B-2 | BLOCK_RECOMMENDATION | Block all new reviews | |
| OD-10-B-3 | Staleness threshold | 24 hours | |
| OD-10-B-4 | Evaluation schedule | Daily + manual override | |

---

## Post-Decision Process

1. Owner marks each decision above (checkbox or specify OTHER).
2. Agent updates this document with final decisions.
3. Agent updates `docs/MASTER_PLAN.md` with recorded decisions.
4. Implementation begins (Sprint 010 Slice B).
5. Decisions can be revisited at any time.

---

## AI Authority Reminder

None of these decisions expand AI authority:

- Guardian reads portfolio data and policy — never modifies either.
- Guardian fires events and notifications — never executes trades.
- BLOCK_RECOMMENDATION is a system safety rail, not an AI decision.
- Owner remains the sole authority for all investment decisions.
