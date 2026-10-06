# Owner Local Test Guide

Open **http://localhost:3802**. No certificate warning, login or API key is needed: the loopback-only Preview uses existing local TEST Owner access. Never enter real credentials or records.

1. Confirm sticky **OWNER PREVIEW / DEMO DATA / NO TRADES** banner.
2. Open Dashboard / Investment Workspace: USD100k demo holdings plus CNY10k cash; no duplicated100k cash deposit.
3. Inspect Household, Portfolio and Policy through Home navigation.
4. Search VTI, QQQ, VXUS, SGOV, BRK.B or Apple; inspect canonical DEMO_EXCHANGE identity.
5. Refresh DEMO prices/FX and inspect provenance. CNY/USD1/7 is a fixed example, not market FX.
6. Monthly contribution is CNY10000. Historical50/30/10/10 candidate is blocked by real Guardian20% concentration; approval remains disabled.
7. For a positive demo, click **Load balanced DEMO targets — existing20% limit**, then **Save targets against published Policy**. Six test targets16.67×five+16.65; no threshold changes or investment advice.
8. Generate contribution candidate; inspect drift, Policy and Guardian. Unclassified-sector warning is preserved.
9. Ask Committee → confirm **local simulated analysis** → **Confirm and run SIMULATED COMMITTEE**. Inspect supporting/opposing reasons, risks and citations; no DeepSeek request.
10. **APPROVE DEMO PLAN** → Decision Journal → select **PREVIEW / SIMULATED** decision → confirmed snapshot and Audit timeline. Refresh to verify persistence. No transaction or execution queue.

API: http://localhost:8002; docs: http://localhost:8002/docs. Normal testing uses the primary URL only.

Developer start: `./scripts/start-owner-preview.sh`; stop: `./scripts/stop-owner-preview.sh` from this dedicated worktree. Stop preserves data volumes and never stops unrelated projects. Do not run `down -v` or copy Preview data to LIVE.
