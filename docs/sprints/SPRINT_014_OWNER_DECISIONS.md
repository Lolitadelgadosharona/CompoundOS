# Sprint 014 — Owner Decisions

> **STATUS: ALL 8 OWNER DECISIONS RESOLVED — READY FOR IMPLEMENTATION**
>
> Sprint 013: COMPLETE
> Sprint 014: OWNER DECISIONS RESOLVED
>
> All decisions preserve: AI advisory only, no trading, no broker,
> no autonomous investment execution.

---

## OD-14-1 — Deployment Target

**Decision:** **Hetzner VPS + Docker + PostgreSQL + Caddy**

- Hetzner CX22 ($5/mo)
- Docker Compose for API + DB
- Caddy reverse proxy with auto-LetsEncrypt
- Future migration path to any VPS provider
- No cloud vendor lock-in

---

## OD-14-2 — Dashboard Technology

**Decision:** **HTMX + Jinja2 + Pico.css**

- Zero JavaScript build step
- Jinja2 templates rendered by FastAPI
- Pico.css for minimal, dark-theme-compatible styling
- 5 pages: Home, Research, Memo, Decisions, Learning
- Owner interaction: symbol input, approve/reject buttons

---

## OD-14-3 — Market Data

**Decision:** **Alpha Vantage V1 — provider abstraction preserved**

- Alpha Vantage free tier (5 calls/min, 25/day)
- Owner provides their own API key via env var
- Existing provider abstraction (Sprint 012-C) unchanged
- Future providers pluggable without code changes

---

## OD-14-4 — Portfolio Source

**Decision:** **CSV import only — no broker integration**

- Owner exports CSV from their broker
- Dashboard upload endpoint (POST /api/portfolio/import)
- Columns: symbol, shares, cost_basis
- No broker credentials, no API connections, no trading

---

## OD-14-5 — Authentication

**Decision:** **Reuse existing X-API-Key architecture**

- Sprint 010-D FastAPI auth middleware
- Environment-based bypass for development/test
- Production must require valid API key
- No password management, no OAuth, no session complexity

---

## OD-14-6 — Backup Strategy

**Decision:** **Daily PostgreSQL backup + restore verification**

- pg_dump scheduled via cron
- Off-site storage (Backblaze B2 or S3-compatible)
- Restore verification test monthly
- Migration files are the schema source of truth

---

## OD-14-7 — Monitoring

**Decision:** **Health checks + logs + basic alerts**

- Health endpoint: GET /health
- UptimeRobot monitoring (free tier)
- Structured logging (JSON to stdout)
- Error alerts on research pipeline failure
- No Prometheus/Grafana complexity for V1

---

## OD-14-8 — First Research Symbol

**Decision:** **Owner-selectable — do not hardcode**

- System accepts any valid symbol
- Owner picks first symbol when dashboard is ready
- No default, no hardcoded ticker
- Pipeline validates symbol before execution

---

## Summary

| ID | Topic | Decision | Impact |
|---|---|---|---|
| OD-14-1 | Deployment | Hetzner VPS + Docker + Caddy | $5/mo |
| OD-14-2 | Dashboard | HTMX + Jinja2 + Pico.css | ~500 lines |
| OD-14-3 | Market data | Alpha Vantage (Owner key) | Free tier |
| OD-14-4 | Portfolio | CSV import | No broker |
| OD-14-5 | Auth | X-API-Key (existing) | No new infra |
| OD-14-6 | Backup | Daily pg_dump + verify | <$2/mo |
| OD-14-7 | Monitoring | Health + UptimeRobot | Free |
| OD-14-8 | Symbol | Owner's choice | Any symbol |

---

## Architecture Preservation

All Sprint 013 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
