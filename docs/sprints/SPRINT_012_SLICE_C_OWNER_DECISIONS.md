# Sprint 012 Slice C — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 012 Slice A: DONE (59d137e)
> Sprint 012 Slice B: DONE (b5444ac)
> Sprint 012 Slice C: DESIGN PHASE — AWAITING OWNER APPROVAL
>
> 5 decisions required before implementation.

---

## OD-12-C-1: Provider Abstraction Strategy

### Owner Direction
Interface-first abstraction. No provider SDK coupling.

### Question
How should provider interfaces be organized?

### Options

| Option | Description |
|---|---|
| A: Single unified interface | One `DataProvider` with methods for all source types. Risk: monolith interface couples unrelated concerns. |
| B: Interface-first, per-source | `MarketDataProvider`, `CompanyDataProvider`, `KnowledgeProvider`, `DocumentProvider`. Each is a standalone Protocol. No SDK dependencies in any interface. |
| C: Plugin architecture | Registry of pluggable providers; each registers capabilities. More flexible but higher complexity budget. |

### Recommendation
**Option B — Interface-first, per-source.** Each data source has
independent semantics, failure modes, and freshness requirements.
Protocol-based interfaces (no ABC dependencies) ensure zero SDK
coupling. Providers can be swapped without changing consumers.

### Owner Decision
- [ ] APPROVE — Option A (Single unified)
- [ ] APPROVE — Option B (Interface-first, per-source — recommended)
- [ ] APPROVE — Option C (Plugin architecture)
- [ ] OTHER: _______________

---

## OD-12-C-2: Caching Strategy

### Owner Direction
Hybrid: market data cache TTL + immutable research evidence snapshot.

### Question
How should external data be cached and evidence preserved?

### Options

| Option | Description |
|---|---|
| A: TTL cache only | market_data_cache with per-data_type expiry. Evidence items reference live cache. Stale cache = stale evidence. |
| B: Immutable snapshot only | No TTL cache. Every provider call creates an immutable committee_evidence_item. Slower, but fully auditable. |
| C: Hybrid TTL + snapshot | market_data_cache for hot reads (hourly/daily reuse). committee_evidence_items snapshot at research time for audit immutability. Cache may expire; snapshot never changes. |

### Recommendation
**Option C — Hybrid.** The `market_data_cache` provides efficient reuse
across research runs (same company analyzed multiple times). The
`committee_evidence_items` table captures an immutable snapshot of
evidence used in each research run for audit. The cache is
disposable; the snapshot is permanent.

Flow:
```
Provider → market_data_cache (TTL: hours to months)
         → EvidenceCollector reads cache at research time
         → committee_evidence_items stores immutable copy
         → Research run references snapshot, not cache
```

### Owner Decision
- [ ] APPROVE — Option A (TTL cache only)
- [ ] APPROVE — Option B (Immutable snapshot only)
- [ ] APPROVE — Option C (Hybrid — recommended)
- [ ] OTHER: _______________

---

## OD-12-C-3: Data Freshness Rules

### Owner Direction
Per data type freshness policy: market price=hours, financial
statements=quarterly, company profile=months.

### Question
What are the TTL rules per data type?

### Proposed Rules

| data_type | TTL | Rationale |
|---|---|---|
| price_history | 6 hours | Price moves intraday; daily decisions need recent quotes |
| overview | 7 days | Company description and sector change slowly |
| income_statement | 90 days | Quarterly filings; new data arrives ~every 90 days |
| balance_sheet | 90 days | Same quarterly cadence as income statement |
| cash_flow | 90 days | Same quarterly cadence |
| sector_performance | 30 days | Sector trends shift monthly |
| fundamentals | 30 days | Aggregate fundamental metrics |
| news | 24 hours | News is time-sensitive but not real-time |

### Recommendation
**Approve the proposed rules.** Aligned with Owner direction:
prices in hours, financial statements in months, profiles in days.
These TTLs are stored in `market_data_cache.expires_at` and are
configurable per data_type.

### Owner Decision
- [ ] APPROVE — Proposed freshness rules as documented
- [ ] OTHER (specify adjustments): _______________

---

## OD-12-C-4: Evidence Provenance Requirements

### Owner Direction
Mandatory provenance envelope: source, provider, timestamp, quality, version.

### Question
What provenance fields are required on every evidence artifact?

### Provenance Envelope

Every evidence artifact (both cached and snapshot) MUST carry:

| Field | Type | Example | Purpose |
|---|---|---|---|
| `source` | str | "alpha_vantage" | Provider identifier |
| `provider` | str | "Alpha Vantage API v2" | Human-readable provider name |
| `source_timestamp` | datetime | 2026-08-10T14:30:00Z | When provider says data is from |
| `retrieved_at` | datetime | 2026-08-10T14:31:22Z | When CompoundOS fetched it |
| `data_quality_status` | str | VALID | Quality classification |
| `provider_version` | str | "v2.0" | API version used |

### Recommendation
**Approve the mandatory envelope.** Full provenance enables:
- Audit: trace every data point to its origin
- Staleness: compare source_timestamp vs now
- Quality degradation: SUSPECT/STALE/FAILED status propagation
- Provider migration: version tracking when APIs change

### Owner Decision
- [ ] APPROVE — Mandatory provenance envelope as documented
- [ ] OTHER (specify): _______________

---

## OD-12-C-5: External Data Failure Handling

### Owner Direction
Graceful degradation: partial evidence allowed, confidence reduced,
no fabricated data.

### Question
What happens when an external data provider is unavailable?

### Options

| Option | Description | Confidence Impact |
|---|---|---|
| A: Fail the run | Provider unavailable → research run fails with error | N/A |
| B: Graceful degradation | Continue with internal data + cache; flag missing sources; reduce confidence | Lowers confidence by 25 pts (missing evidence dimension) |
| C: Use stale cache only | Fall back to expired cache with STALE quality; higher confidence than B but lower data quality | Lowers confidence by 10 pts |

### Recommendation
**Option B — Graceful degradation.** External data enriches but does
not gate AI research. Portfolio data, policy context, guardian status,
and knowledge memory are always available internally. When external
data is missing:
- The evidence bundle has fewer entries
- The EvidenceQuality confidence dimension drops (~25 pts)
- The memo explicitly notes missing external sources
- NO fabricated, guessed, or hallucinated data is substituted

### Owner Decision
- [ ] APPROVE — Option A (Fail entire run)
- [ ] APPROVE — Option B (Graceful degradation — recommended)
- [ ] APPROVE — Option C (Use stale cache)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes + recommends; Owner decides |
| No automatic investment | Decision creation requires Owner POST |
| No trading capability | No trade code paths |
| No fabricated data | Missing external → flagged, not guessed |
| No credentials in code | API keys only in environment variables |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-C-1 | Provider abstraction | Interface-first, per-source Protocols (B) |
| OD-12-C-2 | Caching strategy | Hybrid: TTL cache + immutable evidence snapshot (C) |
| OD-12-C-3 | Data freshness | Per data_type: price=6h, fundamentals=30d, statements=90d |
| OD-12-C-4 | Evidence provenance | Mandatory envelope: 6 fields (source→provider→timestamp→quality→version) |
| OD-12-C-5 | Failure handling | Graceful degradation: partial evidence, reduced confidence, no fabrication (B) |
