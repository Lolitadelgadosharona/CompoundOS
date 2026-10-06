2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# Data rights and evidence retention

VERIFIED FACT: source code retains the following, with no finite automatic expiry for authoritative financial history. Freshness and expiration are eligibility controls, not deletion policies.

| Class | Stored content / tables | Retention and safety purpose |
|---|---|---|
| A CompoundOS-generated facts | Asset UUID, provider mapping/dimensions, ownership, request/session IDs | Indefinite until separately authorized lifecycle change; stable identity/FKs |
| B Derived calculations | contribution_candidates.evidence/content_hash, plan, valuation/FX inputs, drift, effective_policy, Guardian | Immutable candidate evidence; candidate expires at the earlier of one hour or input freshness deadline for approval, record not purged |
| C Provider metadata | instrument_provider_mappings.metadata/provider_id/verified_at; source/as_of/quality/identity | Persisted canonical reconciliation, quote replay/provenance |
| D Provider data | normalized market_observations (price/currency/as_of), fx_rates (rate/pair/quality), optional market_data_cache JSON; research snapshots/evidence may copy normalized data | Full Yahoo chart/search and HTTP response not automatically retained. Normalized observations retained; cache expires logically and can be overwritten, not automatically erased at TTL |
| E AI reasoning | committee_reports.report_content with hash/model/prompt/schema/tokens/cost; investment_memos, perspective_analyses, knowledge memory | Historical reasoning retained; reasoning is not deterministic financial FACT |
| F Citations/evidence | committee_evidence_items structured_facts/hash/as_of/source/reference; research evidence and decision_research_sources links | Immutable report-linked reproducibility; exact registry validation |
| G Policy/Guardian | sealed Policy versions/allocations/rules, Guardian evaluations/events/confirmed results, candidate Policy/Guardian checks | Preserve what was evaluated; no overwrite of published Policy |
| H Journal | decisions, confirmed snapshots/corrections/reviews, contribution_decisions | Original decisions and context remain readable; linked discard records rejection |
| I Audit | audit_events append-only metadata and sequence, audit_log authentication/action metadata, llm_execution_log usage/error records | Durable history; no blanket automatic TTL confirmed. Runtime/platform logs have deployment-specific retention UNKNOWN |

`evidence_collector_v2.CacheService`: price_history6h, news24h, overview168h, fundamentals/sector720h, statements2160h. Legacy research CacheService has analogous horizons and default store168h unless a caller overrides it. Cache TTL determines reuse; it does not erase data copied into Committee/Journal/memory. Backup retention has separate daily/weekly/monthly/locked categories; the newest verified backup remains locked. It does not implement market-data deletion rights.

RECOMMENDATION: retain canonical IDs, source reference, as_of, normalized required values/quality, calculation inputs/outputs, evidence IDs/hashes and governance decisions; avoid unnecessary full provider payloads. Current V1 Yahoo adapter already follows normalized storage. Do not remove old evidence or alter immutable financial history to make an unsupported retention promise. No schema/history changes performed by RC.

OPEN QUESTION / OWNER ACTION: obtain explicit authorization for current indefinite normalized/derived evidence retention, including backup copies and disclosure to required AI provider. If provider permission requires bounded deletion incompatible with current immutable evidence, keep that source disabled and choose a suitable licensed source or separately review a retention design before launch. Merely retaining a hash is not enough to reproduce valuation and does not automatically solve rights requirements.

The [DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) discusses input/output processing, improvement/training and variable retention; it does not establish zero retention for this deployment. Confirm applicable open-platform terms, opt-out/retention arrangements and disclosure of portfolio/Policy facts. No confidential real Owner evidence was transmitted in this sprint.

Owner-only UI/API is not public redistribution; there is no V1 public market-data API or public evidence share flow verified. Export/download/backups and sending facts to LLMs still require applicable rights. No claim of legal compliance is inferred from personal use alone.


2026-10-05 final readiness update: exact per-field MUST/SHOULD/MAY/SHOULD NOT recommendations and durations are in RETENTION_POLICY_RECOMMENDATION.md. These are Owner-review recommendations, not license acceptance or automatic purge implementation. Existing authoritative financial records remain intact.
