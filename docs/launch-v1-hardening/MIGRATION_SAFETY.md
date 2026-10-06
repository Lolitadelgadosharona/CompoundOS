# Migration safety and rollback

VERIFIED FACT: `0035_launch_foundation` is additive and its immutable evidence/FK constraints are retained. Its parser now accepts a strict UUID structure and compares uppercase historical markers case-insensitively. `0036_launch_hardening` adds nullable observation/FX identity and FX quality, repairs the capture function for databases that already applied 0035, and additively captures previously missed uppercase research links. It does not rewrite positions, native currency ledgers, Asset UUIDs, published Policy or decision snapshots.

Compatibility: legacy observations without verified identity remain readable and are not trusted for new recommendations. Mutation gate and health schema head advance together to 0036. Generic discard of linked drafts records rejection and retains immutable links/history; unlinked ordinary drafts retain the original discard behavior.

INTEGRATION VERIFIED: empty downgrade to 0034; non-empty upgrade with both lowercase and uppercase markers; existing household/Policy/decision/memo rows retained; safe refusal of populated downgrade; retained link after historical discard; isolated pg_dump/pg_restore into another newly created test DB. This is not a production-data migration rehearsal.

Forward-only after evidence exists: 0035 refuses downgrade when launch evidence tables are populated. 0036 refuses removal of identity columns once verified evidence exists. Do not bypass these checks. Old app images expecting 0034/0035 cannot resume writes against 0036; readonly behavior is not a complete operational rollback.

Before any future Owner-authorized deployment: stop writes and workers, record application SHA/schema, take an encrypted full logical backup plus roles/configuration, restore it to isolated staging, compare counts/history/constraints, and rehearse this upgrade there. Abort before production migration if restore is unproven, schema differs, malformed identity cannot be reconciled, required inputs are missing, or launch provider/legal gates fail.

Rollback: first prefer a schema-compatible hardened app image with workers stopped and new recommendation generation disabled. For pre-migration restoration, restore the verified full backup into a new database and switch the application only after integrity checks. Reconcile any post-backup writes separately; do not erase them silently. Snapshot all post-migration evidence before any such recovery. Do not run destructive downgrade or restore over the only database.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
