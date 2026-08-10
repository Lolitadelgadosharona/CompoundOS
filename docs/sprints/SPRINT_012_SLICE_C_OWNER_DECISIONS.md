# Sprint 012 Slice C — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 012 Slice A: DONE (59d137e)
> Sprint 012 Slice B: DONE (b5444ac)
> Sprint 012 Slice C: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 5 decisions required before implementation.

---

## OD-12-C-1: Provider Abstraction Strategy

### Question
How should provider interfaces be organized?

### Options

| Option | Description |
|---|---|
| A: Single unified interface | One `DataProvider` with methods for all source types |
| B: Separate per-source interfaces | `MarketDataProvider`, `CompanyDataProvider`, `KnowledgeProvider`, `DocumentProvider` (as designed) |
| C: Plugin architecture | Registry of pluggable providers; each registers capabilities |

### Recommendation
**Option B — Separate per-source interfaces.** Each data source has
different semantics, failure modes, and freshness requirements.
Separate interfaces allow independent evolution and testing.
Rigid monolithic interfaces would force coupling between unrelated
data sources.

### Owner Decision
- [ ] APPROVE — Option A (Single unified)
- [ ] APPROVE — Option B (Separate per-source — as designed)
- [ ] APPROVE — Option C (Plugin architecture)
- [ ] OTHER: _______________

---

## OD-12-C-2: Caching Strategy for External Data

### Question
How should external data be cached?

### Options

| Option | Description |
|---|---|
| A: Always cache | Every provider call stores result in market_data_cache. TTL by data_type. |
| B: Cache selectively | Cache fundamentals and overviews; don't cache real-time price data. |
| C: No caching in Slice C | Cache strategy deferred to when real providers exist. |

### Recommendation
**Option C — No caching implementation in Slice C.** Slice C defines
interfaces only. Caching behavior is configured per provider when real
implementations exist (Sprint 013+). The `market_data_cache` table
provides the storage infrastructure; caching logic belongs to the
provider, not the interface.

### Owner Decision
- [ ] APPROVE — Option A (Always cache)
- [ ] APPROVE — Option B (Selective caching)
- [ ] APPROVE — Option C (Defer caching to Sprint 013)
- [ ] OTHER: _______________

---

## OD-12-C-3: Data Freshness Rules

### Question
What are the default freshness rules for external data?

### Options

| Option | Price | Fundamentals | Sector | Overview |
|---|---|---|---|---|
| A: Aggressive | 1 hour | 7 days | 7 days | 24 hours |
| B: Moderate | 6 hours | 30 days | 30 days | 7 days |
| C: Conservative | 24 hours | 90 days | 90 days | 30 days |

### Recommendation
**Option B — Moderate.** Aligned with OD-12-12 from Sprint 011 TD.
Family office makes occasional decisions, not daily trading.
6-hour price data and monthly fundamentals are sufficient for V1.

### Owner Decision
- [ ] APPROVE — Option A (Aggressive)
- [ ] APPROVE — Option B (Moderate)
- [ ] APPROVE — Option C (Conservative)
- [ ] OTHER: _______________

---

## OD-12-C-4: Provenance Requirements

### Question
What provenance must every external data artifact carry?

### Options

| Option | Required Fields |
|---|---|
| A: Minimal | source, retrieved_at |
| B: Standard | source, source_timestamp, retrieved_at |
| C: Full | source, source_timestamp, retrieved_at, data_quality_status, provider_version |

### Recommendation
**Option B — Standard.** `source` and timestamps are essential for audit
and staleness detection. `data_quality_status` (Option C) is available
on market_data_cache but belongs to the caching layer, not individual
provider responses. `provider_version` is useful when APIs change but
adds overhead.

### Owner Decision
- [ ] APPROVE — Option A (Minimal: source, retrieved_at)
- [ ] APPROVE — Option B (Standard: + source_timestamp)
- [ ] APPROVE — Option C (Full: + quality + version)
- [ ] OTHER: _______________

---

## OD-12-C-5: External Data Failure Handling

### Question
What happens when an external data provider is unavailable?

### Options

| Option | Description |
|---|---|
| A: Fail the research run | If Alpha Vantage is down, the entire run fails with error "external data unavailable" |
| B: Continue without external data | Use only internal data (portfolio, policy, knowledge memory); flag missing external data in evidence |
| C: Use stale cached data | Fall back to expired cache entries with data_quality_status=STALE |

### Recommendation
**Option B — Continue without external data.** External data enriches
but does not gate research. Portfolio, policy, guardian, and knowledge
memory data are always available internally. The perspective analysis
generates whatever it can with available evidence. The memo notes
missing external sources.

### Owner Decision
- [ ] APPROVE — Option A (Fail run)
- [ ] APPROVE — Option B (Continue without external)
- [ ] APPROVE — Option C (Use stale cache)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes + recommends; Owner decides |
| No automatic investment | Decision creation requires Owner POST |
| No trading | No trade code paths |
| No credentials in code | API keys only in environment variables |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-C-1 | Provider abstraction | Separate per-source interfaces (B) |
| OD-12-C-2 | Caching strategy | Defer to Sprint 013 (C) |
| OD-12-C-3 | Data freshness rules | Moderate: 6h/30d/30d/7d (B) |
| OD-12-C-4 | Provenance requirements | Standard: source + 2 timestamps (B) |
| OD-12-C-5 | External failure handling | Continue without external data (B) |
