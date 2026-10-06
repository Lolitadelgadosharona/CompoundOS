2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# Rollback or restore runbook

VERIFIED FACT: populated launch evidence is forward-only.0035 refuses dropping populated launch tables;0036 refuses removing populated verified observation fields. Existing expected-head mutation gates mean an old0034 app cannot safely resume writes/workers against0036. Empty downgrade passing is not a populated rollback guarantee.

Before any future migration: Owner approval, known deployed SHA/schema, freeze all writes/workers, timestamped encrypted full pg_dump plus roles/config, integrity hash, isolated restore verification and documented cutover/reconciliation plan. Record post-backup boundary; abort if backup/restore fails, identity/Policy cannot reconcile, unsupported schema, staging/provider gates fail or storage/lock budget unacceptable. Do not run irreversible operations first and ask later.

Preferred recovery is roll forward or a previously tested schema-compatible hardened application image, with new recommendations/workers disabled until verified. Keep immutable history, normalized observations, canonical UUID/FKs and Policy/Journal.

If full restoration becomes unavoidable, restore the approved pre-migration backup into a NEW database, verify IDs/counts/constraints/hashes and old-schema app compatibility, preserve the failed database and any post-backup decisions/audits for reconciliation, then perform an Owner-approved switch. Restoring an old backup alone loses post-backup history unless reconciled; do not silently discard it. Never drop/overwrite the only database, force populated downgrade or rewrite financial snapshots.

Isolated verified recipe (not production authorization): `pg_dump -Fc` of the synthetic migrated test DB → newly created different `_test` DB → `pg_restore` → compare all original column row hashes and actual alembic_version, links and counts. Current package includes synthetic dump and validation. Production encrypted restore, RPO/RTO and compatible image rollback remain NOT VERIFIED until the actual staging/baseline is supplied.
