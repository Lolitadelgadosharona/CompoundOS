# CompoundOS — MVP Deployment Runbook

This runbook takes a fresh VPS to a fully operational CompoundOS
deployment. Follow the steps in order; each step is verifiable.

---

## 1. VPS prerequisites

- A Linux VPS (Ubuntu 22.04 LTS recommended) with ≥ 2 GB RAM, ≥ 20 GB disk.
- A domain name pointed at the VPS (for the Caddy HTTPS reverse proxy).
- SSH access as a non-root user with sudo.
- Ports 80 and 443 reachable from the internet.

## 2. Docker installation

Install Docker Engine + the Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# log out and back in so the group takes effect
docker --version && docker compose version
```

## 3. Repository setup

```bash
git clone https://github.com/Lolitadelgadosharona/CompoundOS.git
cd CompoundOS
```

## 4. Environment configuration

```bash
cp .env.example .env
# EDIT .env and set real values:
#   DB_PASSWORD       — strong, unique postgres password
#   ENVIRONMENT       — production
#   ANTHROPIC_API_KEY — your Anthropic API key
#   OPENAI_API_KEY    — your OpenAI API key
#   AV_API_KEY        — your AlphaVantage API key
#   CADDY_DOMAIN      — your domain (e.g. compoundos.example.com)
```

Never commit `.env` (it is gitignored). Verify no secrets are tracked:

```bash
git status --short   # .env must NOT appear
```

## 5. Docker compose startup

```bash
docker compose up -d --build
docker compose ps          # api, db, redis, caddy all "Up"
```

The API entrypoint runs `alembic upgrade head` automatically before
starting (see §6).

## 6. Migration flow

Migrations run automatically at container start (via `scripts/entrypoint.sh`).
Verify the schema is at the expected head:

```bash
docker compose logs api | grep -i migration
# or check the readiness endpoint (§10)
```

If a migration fails, the API container exits non-zero (fail-closed) and
does NOT start — fix the error and restart with `docker compose up -d`.

Manual migration (rarely needed):

```bash
docker compose run --rm api alembic upgrade head
```

## 7. Owner key bootstrap

Create the FIRST Owner API key (works only when no key exists yet):

```bash
docker compose run --rm api python -m apps.api.bootstrap_key
```

Copy the printed key immediately — it is shown exactly once. Store it
securely; use it in the `X-API-Key` header for all subsequent calls.

Additional keys (after the first) are created via:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/keys?label=ops \
     -H "X-API-Key: $OWNER_KEY"
```

## 8. Household creation

Create the singleton household profile (required before research):

```bash
curl -X POST http://127.0.0.1:8000/api/household \
     -H "Content-Type: application/json" \
     -H "X-API-Key: $OWNER_KEY" \
     -d '{"household_name":"Family Office","base_currency":"USD"}'
```

## 9. Prompt approval

Prompt templates are seeded as DRAFT and must be Owner-approved before
research can run. List drafts and approve each:

```bash
curl http://127.0.0.1:8000/api/prompts -H "X-API-Key: $OWNER_KEY"
# for each prompt id in the list:
curl -X POST http://127.0.0.1:8000/api/prompts/<ID>/approve \
     -H "X-API-Key: $OWNER_KEY"
```

## 10. Readiness verification

Confirm the system reports READY:

```bash
curl http://127.0.0.1:8000/api/setup/status -H "X-API-Key: $OWNER_KEY"
```

Expected: `{"overall":"ready","remaining_steps":[]}`. If `pending`,
follow the listed `remaining_steps` until READY. The dashboard
(`https://<CADDY_DOMAIN>/setup`) shows the same checklist.

## 11. Backup configuration

Backups write to `./backups` (bind-mounted into the API container),
encrypted with `age`, then verified. Schedule daily backups:

```bash
# create a host cron (runs at 02:00 daily)
echo '0 2 * * * cd /path/to/CompoundOS && ./scripts/backup.sh' | crontab -
```

Or trigger manually via the backup endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/backup \
     -H "X-API-Key: $OWNER_KEY"
```

## 12. Restore drill

Practice recovery before you need it:

1. Locate the latest encrypted backup in `./backups`.
2. Decrypt and restore into a scratch Postgres.
3. Run `alembic upgrade head` against the restored DB.
4. Verify via `/api/setup/status` that schema/owner/household are intact.

The health endpoint reports restore-verification status:

```bash
curl http://127.0.0.1:8000/api/health/full -H "X-API-Key: $OWNER_KEY"
```

---

## Post-deploy checklist

- [ ] `.env` populated (no placeholders)
- [ ] `docker compose ps` — all services Up
- [ ] Migrations applied (api logs)
- [ ] First owner key created + stored
- [ ] Household created
- [ ] 7 prompts approved
- [ ] `/api/setup/status` → ready
- [ ] Backup cron scheduled
- [ ] Restore drill completed
