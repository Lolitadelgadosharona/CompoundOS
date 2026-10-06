# Minimal staging runbook

Use `docker compose --project-name compoundos-v1-readiness-staging -f docker-compose.staging.yml` only; never combine with production Compose or attach production volumes. Provide private COMPOUNDOS_STAGING_DB_PASSWORD and exact reviewed COMPOUNDOS_STAGING_API_IMAGE / WEB_IMAGE via secure environment. The task stage controller injects only synthetic test credentials and redacts its output. Do not store realAI credentials in this controller's private test JSON file.

Create fresh DB through isolated Compose. Explicitly run the reviewed image's Alembic upgrade against the new `_test` database; API startup auto-migrations remain off. Start API/Web/Caddy, export ONLY `/data/caddy/pki/authorities/local/root.crt` from this stage Caddy, and verify HTTPS hostname/CA with a client-specific trust context. Do not change the OS trust store or ignore TLS validation.

Bootstrap first test Owner key with the existing API bootstrap module; capture its one-time value privately, not an evidence log. Use it to create a Secure/HttpOnly/Strict browser session over this staging HTTPS origin. Only synthetic Owner/ledger data is seeded. The default staging template deliberately omits live provider credentials/permission and keeps data gates closed.

For later Owner-provisioned real verification, use a separately reviewed private override/secret manager that supplies required DeepSeek model/rates/key and verified market permission. Preserve actual source identities and normal freshness; no test adapter, placeholder FX, synthetic quote or demo Committee may become a production trusted source. User must supply documentary permission before enabling a data safety switch.

Recovery rehearsal uses a separately created staging-cluster test DB: seed valid0034 history, snapshot old-column hashes, migrate0036, validate IDs/counts/FKs, take pg_dump, restore to another new test DB, compare. Do not force populated downgrade. Keep financial history and post-backup records if a real restore is ever authorized.

Stop/remove only this named staging project when no longer needed. Do not run `down -v` unless Owner explicitly wants disposal of synthetic stage data and its backup is accounted for. Never stop other projects or production. Exact source SHA, image labels/digests, actual HTTPS version, health schema and environment belong in final evidence manifest. If PR merge changes SHA, rebuild/reverify the approved merged SHA before any future production authorization.
