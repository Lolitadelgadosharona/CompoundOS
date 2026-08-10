# Sprint 010 Slice C — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 010 Slice C Design: COMPLETE (9a7d606)
> 4 decisions require Owner review before implementation begins.

---

## OD-10-C-1: High-Impact Decision Threshold

### Question
At what portfolio allocation percentage should a decision be classified as
"high-impact," triggering mandatory post-decision reviews (30d, 90d, 1yr)?

### Context
The Learning Loop (Slice C) auto-schedules reviews for high-impact decisions.
Low-impact decisions remain optional — the Owner schedules reviews manually.
This threshold determines which decisions get automatic review tracking.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: 5%** | Decisions representing >5% of portfolio trigger auto-reviews | Catches meaningful decisions early; small enough for a concentrated portfolio | More review noise for active traders |
| **B: 10%** | Decisions >10% trigger auto-reviews | Less noise; focuses on genuinely large decisions | May miss important but smaller decisions (e.g. a new asset class entry at 7%) |
| **C: Manual only** | Owner explicitly classifies each decision impact | Maximum control; no false positives | Requires Owner to remember; no systemic safeguard |

### Architecture Impact
- Option A/B: `review_service.py` checks `investment_idea.proposed_allocation_pct > THRESHOLD`. Configuration constant.
- Option C: No auto-classification; all decisions default to low-impact.

### Future Scalability
The threshold is a single constant. It can be changed at any time without
schema changes. Future enhancement: per-decision-type thresholds (e.g.
different thresholds for new positions vs adding to existing positions).

### Recommendation
**Option A — 5%.** A 5% portfolio move is significant for a family office.
This threshold ensures that any meaningful allocation change is tracked
with scheduled reviews. The Owner can always manually schedule additional
reviews for smaller decisions.

### Owner Decision
- [ ] APPROVE — Option A (5% threshold)
- [ ] APPROVE — Option B (10% threshold)
- [ ] APPROVE — Option C (Manual classification only)
- [ ] OTHER (specify): _______________

---

## OD-10-C-2: Activity Feed Size

### Question
How many recent activity items should the dashboard return?

### Context
The Activity Feed section of the dashboard shows recent events across all
systems: position imports, transactions, Guardian events, Committee reports,
and decisions. This determines the feed length.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: 20 items** | Return last 20 activity items | Quick response; focused view; fits one screen | May miss context on busy days |
| **B: 50 items** | Return last 50 items | More historical context | Larger response; more scrolling |
| **C: Paginated** | /api/activity?page=1&size=20 with total count | Scalable; frontend can load more on demand | More complex API; adds pagination metadata |

### Architecture Impact
- Option A/B: Hardcoded LIMIT in SQL query. Single constant.
- Option C: Requires pagination params, total count query, PageResponse wrapper.

### Future Scalability
Option C is the most future-proof but adds complexity. Option A is trivially
upgradeable to Option C later — just change the endpoint to accept page/size
params and wrap the response.

### Recommendation
**Option A — 20 items.** For a single-owner family office dashboard, 20 items
provides the right balance of context and focus. The endpoint can be upgraded
to pagination later if the activity volume grows. Start simple.

### Owner Decision
- [ ] APPROVE — Option A (20 items)
- [ ] APPROVE — Option B (50 items)
- [ ] APPROVE — Option C (Paginated)
- [ ] OTHER (specify): _______________

---

## OD-10-C-3: FX Rate Gap Handling

### Question
How should the dashboard handle positions in currencies where no FX rate
is available for conversion to the base currency?

### Context
The Owner may hold positions in HKD, CNY, EUR, etc. The HouseholdProfile
defines a base currency (e.g. USD). FX rates are stored in `fx_rates` but
may have gaps — no rate exists for a specific currency pair, or the most
recent rate is stale.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Flag as unconverted** | Report the value in native currency; flag the section with "unconverted_currencies: [HKD, CNY]" | Transparent; Owner sees exactly what's unconverted; no silent errors | Total net worth may be incomplete until rates are provided |
| **B: Use latest available with warning** | Use the most recent rate for that pair regardless of age; include a warning | Net worth always shows a number; less alarming | Stale rates produce misleading totals; 3-month-old HKD rate could misrepresent value |
| **C: Hide affected assets** | Exclude positions without FX rates from the dashboard entirely | Clean display | Silently hides assets; Owner may not realize positions exist |

### Architecture Impact
- Option A: `by_currency` section includes unconverted currencies. Total value
  is "sum of converted + note about unconverted." No rate fallback needed.
- Option B: Extends `get_latest_fx_rate` to ignore timestamp; adds warning field.
- Option C: Filters positions WHERE currency has a rate available. Risky.

### Future Scalability
Option A is the safest foundation. When automated FX rate feeds are added
(future sprint), gaps become rarer. The flagging mechanism remains useful
for data quality monitoring even with live rates.

### Recommendation
**Option A — Flag as unconverted.** Transparency is a core CompoundOS principle.
The dashboard should never silently substitute data. If a conversion rate is
missing, the Owner should know exactly what's unconverted and why. This also
provides a natural prompt to import FX rates.

### Owner Decision
- [ ] APPROVE — Option A (Flag as unconverted)
- [ ] APPROVE — Option B (Latest available with warning)
- [ ] APPROVE — Option C (Hide affected assets)
- [ ] OTHER (specify): _______________

---

## OD-10-C-4: Dashboard Response Strategy

### Question
Should the dashboard return a full snapshot on every request, or should
sections be requestable individually?

### Context
The dashboard aggregates data from 7+ tables across 4 sprints. A full
snapshot computes everything at once. Individual section endpoints allow
the frontend to load sections independently.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Full snapshot** | GET /api/dashboard returns all 7 sections in one response | Single request; atomic snapshot; simpler frontend | Larger response; sections that haven't changed are re-computed |
| **B: Cached snapshot** | Compute once, cache for N minutes, serve from cache | Fast response; reduced DB load | Stale data risk; cache invalidation complexity |
| **C: Tiered (section endpoints)** | GET /api/dashboard/net-worth, /allocation, /risks etc. | Load only what's needed; smaller responses | Multiple round-trips; no atomic snapshot guarantee |

### Architecture Impact
- Option A: One endpoint, one service function. ~250 lines.
- Option B: Requires cache layer (Redis or in-memory dict); invalidation on
  import/Guardian evaluation.
- Option C: 7+ endpoints; each independently queryable. ~500 lines.

### Future Scalability
Per OD-10-1 (Tiered approach approved): Live computation for real-time data
(net worth, allocation, compliance, risks). Cached analytics for historical
reports. Option A aligns with this decision — live full snapshot for the
dashboard, caching deferred to analytics sprint.

### Recommendation
**Option A — Full snapshot.** A single GET /api/dashboard returning all
sections is the simplest and most coherent design. The Owner sees a
complete, internally consistent view of their wealth. For a single-owner
family office with <100 positions, the query cost is negligible.

### Owner Decision
- [ ] APPROVE — Option A (Full snapshot)
- [ ] APPROVE — Option B (Cached snapshot)
- [ ] APPROVE — Option C (Tiered section endpoints)
- [ ] OTHER (specify): _______________

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-10-C-1 | High-impact threshold | 5% of portfolio (A) | |
| OD-10-C-2 | Activity feed size | 20 items (A) | |
| OD-10-C-3 | FX rate gap handling | Flag as unconverted (A) | |
| OD-10-C-4 | Dashboard response | Full snapshot (A) | |

---

## Post-Decision Process

1. Owner marks each decision above (checkbox or specify OTHER).
2. Agent updates this document with final decisions.
3. Agent updates `docs/MASTER_PLAN.md` with recorded decisions.
4. Implementation begins (Sprint 010 Slice C).
5. Decisions can be revisited at any time.

---

## AI Authority Reminder

None of these decisions expand AI authority:

- Dashboard is read-only — AI reads, never writes.
- Learning Loop is Owner-driven — outcomes are recorded by the Owner.
- No automatic investment decisions, trading, or policy modification.
- Owner remains the sole authority for all financial decisions.
