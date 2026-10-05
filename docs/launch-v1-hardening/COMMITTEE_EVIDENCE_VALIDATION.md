# Committee evidence validation

VERIFIED FACT: Each evaluation builds a context registry from persisted evidence. It checks session ownership, allowed source type, provenance, citation reference, as_of/future time and deterministic content hash. Current internal, historical and simulated classifications are explicit. Older external evidence is historical, never labeled live. Model citations must contain exactly the supplied ID, reference and classification-bearing claim. Unknown, unrelated, empty or modified citations fail.

All quantitative financial facts remain in deterministic evidence. Runtime rejects generated numeric assertions; English cardinals/fold quantities and common Chinese numeric notation are rejected across reports; contribution prompt also rejects spelled numbers and requires qualitative confidence. Model narrative is inference, direction is recommendation. The hardened contribution prompt is `contribution-v1.1`, reports use schema `hardening-1`. Pre-hardening reports cannot authorize a new contribution plan.

Generic research approvals must cite this run's evidence and the current target/valuation/Policy context in a completed validated report. Draft wrappers and historical unvalidated reports cannot bypass that gate. New research wrapper evidence has a real deterministic hash rather than a random UUID. Existing immutable history is preserved.

Atomic queued→running claim prevents duplicate provider calls even with a stale ORM object. Provider/preflight/parse/output failures mark the claimed evaluation failed. Production accepts DeepSeek only; synthetic provider exceptions are confined to explicit test injection. Budget checks require configured positive input/output prices, cover all allowed attempts before the network call, validate usage and record successful-response cost. Failed attempts may have unknown billed cost; the preflight ceiling is the safety control, not a claim of precise total billing.

The network boundary requests JSON output, limits response size, rejects malformed, truncated, empty or invalid-usage responses, and bounds timeout/output. Evidence strength: UNIT plus synthetic PostgreSQL INTEGRATION. Real DeepSeek remains NOT VERIFIED.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
