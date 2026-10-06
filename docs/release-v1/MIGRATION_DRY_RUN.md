2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# Migration dry run

VERIFIED FACT: no new migration added in RC. Reviewed0035 creates additive launch tables, strict UUID research-link parser/backfill and immutable triggers;0036 adds nullable quote/FX identity/quality and repairs old parser/backfill. Neither upgrade deletes financial rows or guesses identities into old observations.

New synthetic isolated PostgreSQL database migrated0034→0036. It contained Household, published/sealed Policy, Portfolio/account/native position/cash/Asset UUID, historical Committee report, research memo/draft, confirmed Journal snapshot and AuditEvents. All legacy-table original columns were snapshotted and content hashes/counts matched exactly after upgrade. Research link was added, no duplicate latest position introduced. The first fixture attempt was rejected by the existing decision lifecycle consistency trigger; it was corrected by seeding a separate valid confirmed historical decision in another fresh test DB. Production code/triggers were not relaxed.

A populated downgrade was safely refused. Custom-format pg_dump was restored to a newly created separate test DB; all legacy-table hashes/UUIDs/counts plus schema0036 and research link matched. Empty downgrade and uppercase/malformed marker regressions are covered by the full suite/hardening counterexamples.

INTEGRATION VERIFIED: synthetic upgrade/readability/recovery. NOT VERIFIED: actual deployed SHA/schema, a deidentified authorized production clone, volume/lock timings, production encrypted backup and recovery time. This local rehearsal does not authorize production migration. See restore runbook for prerequisites and abort criteria.

Final readiness adds actual local staging PostgreSQL-cluster rehearsal with distinct fresh0034 source-copy and0036 restore databases.59 original-column table hashes/UUIDs/counts and research link/FK validation match. Initial restore tooling omitted Docker stdin forwarding; corrected `docker exec -i` and used another newly created restore DB. No application migration or constraint was relaxed to satisfy the probe. Actual production recovery remains NOT VERIFIED.
