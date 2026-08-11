# Sprint 014 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 013: COMPLETE
> Sprint 014: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## OD-14-1 — Deployment Target

**Question:** Where should CompoundOS V1 be deployed?

**Options:**
- A) Hetzner CX22 ($5/mo, 2 vCPU, 4GB RAM, 40GB SSD) — single VM, self-contained
- B) Fly.io free tier — limited resources, simpler deploy, US-only free tier
- C) Railway / Render free tier — managed, simpler but less control
- D) Local-only for now, deploy later

**Recommendation:** **A — Hetzner CX22.** Single VM is sufficient for a solo-Owner system. Gives us full control, fixed cost, and room to grow to Postgres + Docker.

**Budget:** ~$5/mo, $60/year

---

## OD-14-2 — Dashboard Technology

**Question:** What frontend stack should the Owner Dashboard use?

**Options:**
- A) HTMX + Jinja2 + Pico.css (~100 lines per page, no build step)
- B) React + Vite (rich UI, heavier, more complex to maintain solo)
- C) Gradio (Python-native, fast to build, limited customization)
- D) No dashboard — continue using CLI + test output only

**Recommendation:** **A — HTMX + Jinja2 + Pico.css.** Minimal dependencies, no JavaScript build step, works with existing FastAPI backend. Suitable for a solo-Owner who wants functional, not flashy.

---

## OD-14-3 — Real Market Data in V1

**Question:** Should the first real investment workflow use Alpha Vantage or continue with mock data?

**Options:**
- A) Alpha Vantage free tier (5 calls/min, 25/day) — real data, limited throughput
- B) Continue mock data — validate workflow without API dependency
- C) Use a commercial provider (Tiingo, Polygon.io, etc.)

**Recommendation:** **A — Alpha Vantage free tier.** Sprint 013 built the infrastructure. V1 should exercise it. 25 calls/day is sufficient for 2-4 research runs/day. We can upgrade later.

**API Key:** The Owner must provide their own free Alpha Vantage key. This key is never stored in the repo.

---

## OD-14-4 — Portfolio Data Source

**Question:** How does the Owner's portfolio enter CompoundOS?

**Options:**
- A) Manual CSV import (Owner exports from their broker, imports via dashboard)
- B) Direct broker API (requires credentials — violates current security policy)
- C) Manual entry via dashboard form (holdings: symbol, shares, cost basis)
- D) Skip portfolio context entirely for V1

**Recommendation:** **A — Manual CSV import.** Avoids broker credentials. Owner controls what data enters the system. Portfolio context is critical for investment decisions. A simple CSV (symbol, shares, cost_basis) is all we need.

---

## OD-14-5 — Dashboard Authentication

**Question:** How does the Owner authenticate to the dashboard?

**Options:**
- A) Simple API key in URL/handler (Bearer token)
- B) Password + session (cookie-based, FastAPI built-in)
- C) OAuth (Google/GitHub) — overkill for solo-Owner
- D) No authentication (local-only, trusted network)

**Recommendation:** **B — Password + session.** FastAPI has built-in support. Solo-Owner creates one account. Session persists. Simple and sufficient.

**Credential:** One hardcoded admin user in `.env` — `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

---

## OD-14-6 — Backup Strategy

**Question:** How often and where should backups be stored?

**Options:**
- A) Daily pg_dump to Backblaze B2 (~$0.005/GB/mo) — off-site, $1-2/mo
- B) Daily pg_dump to local VM only — no off-site, risk of VM failure
- C) Weekly manual backup — Owner exports manually
- D) No backup — accept risk for V1

**Recommendation:** **A — Daily pg_dump to Backblaze B2.** Off-site is essential for financial data. Tiny cost. Simple to automate (cron + rclone).

---

## OD-14-7 — Monitoring

**Question:** What monitoring is required for V1?

**Options:**
- A) UptimeRobot (free) + Sentry (free tier) — health check + error tracking
- B) Prometheus + Grafana (self-hosted on VM) — more data, more maintenance
- C) None — check manually if something seems wrong

**Recommendation:** **A — UptimeRobot + Sentry.** Free, zero-config, covers the basics. Owner gets notified if the API is down or if errors occur.

---

## OD-14-8 — First Real Investment Symbol

**Question:** What symbol should be used for the first real end-to-end research run?

**Options:**
- A) AAPL — widely analyzed, lots of public information, good baseline
- B) An ETF (VOO, SPY) — simpler analysis, index-level reasoning
- C) A stock the Owner already holds — immediate portfolio context
- D) Don't specify — pick any symbol at runtime

**Recommendation:** **D — Don't specify now.** The system should work with any symbol. The Owner will pick one when the dashboard is ready.

---

## Summary

| ID | Topic | Recommendation | Impact |
|---|---|---|---|
| OD-14-1 | Deployment | Hetzner CX22 | $5/mo |
| OD-14-2 | Dashboard | HTMX + Jinja2 + Pico.css | ~500 lines HTML |
| OD-14-3 | Market data | Alpha Vantage (Owner key) | Free tier |
| OD-14-4 | Portfolio source | CSV import | No broker creds |
| OD-14-5 | Authentication | Password + session | .env config |
| OD-14-6 | Backup | Daily to B2 | <$2/mo |
| OD-14-7 | Monitoring | UptimeRobot + Sentry | Free |
| OD-14-8 | First symbol | Owner's choice | Any symbol |
