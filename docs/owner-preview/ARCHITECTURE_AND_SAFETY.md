# Owner Preview safety and implementation

Dedicated branch codex/compoundos-owner-preview, based on9ed4d55. No push toPR121, merge or production deployment.

Explicit COMPOUNDOS_PREVIEW_MODE=true defaultsfalse. Startup requires ENVIRONMENT=test and database compoundos_owner_preview_test. Production+preview fails before serving; Preview database with mode disabled also fails. Separate Compose project/PG/Redis volumes, only loopback8002/3802 published. Existing test-mode Owner role permits no-key local access; foreign Host/Origin and external/execution API routes are denied. No public exposure or worker.

Existing compose.yaml plus overlays are reused. When exact9ed4d55 local RC images exist, revision-checked cached dependencies are reused with this branch's API and freshly compiled frontend bound read-only. This avoided a Docker Hub registry EOF. Otherwise existing Dockerfiles build normally. Cached image labels identify base dependencies, runtime source SHA identifies this branch. Generated local password0600 resides outsideGit; never printed. No real provider keys supplied.

DemoProvider centralizes six canonical identities (DEMO_EXCHANGE/DEMO_PROVIDER), constant controlled prices and fixedUSD/CNY7+reciprocal. Observation clock is local, rounded to seconds for freshness; DEMO quality never denotes live observation. Preview seed alone extends two Preview-DB CHECK constraints to admit DEMO; production migrations unchanged, no immutable trigger disabled. LIVE quality/source gates reject DEMO. Existing IDs and Owner/staging data remain untouched. All records are confined to this explicitly named Preview DB; no promotion/import path provided.

Real valuation/contribution arithmetic, Policy20% limit, Guardian20% position/40% sector rules and all evidence/numeric/schema validation remain active. USD100k holdings+CNY10k monthlycash seeded, initial-capital configuration is not another deposit. Original50/30/10/10 candidate is correctly concentration-blocked. Six balanced test targets enable positive demonstration without changing thresholds; sector warning remains visible.

PreviewCommittee implements the real AIModelProvider interface and consumes the actual evidence registry. Deterministic qualitative output copies exact citations through run_committee; no DeepSeek construction or external financial calls. Empty registry gives insufficient evidence. Reports identify SIMULATED_COMMITTEE; evidence data_mode SIMULATED and valuation data_mode DEMO. No numerical invention or validation bypass.

Preview approval reuses immutable Journal architecture in the Preview namespace: title PREVIEW/SIMULATED, return execution PREVIEW_ONLY; contribution audit actions preview.* with data_modeSIMULATED/execution_allowedfalse. Existing Journal confirmed status is confined to Preview records, never a LIVE recommendation. Generic Journal audit rows inherit the separate DB namespace. No execution adapter, queue or transaction is created.

Frontend sticky banner on every page; legacy HTML equivalent banner, API headerX-CompoundOS-Data-Mode:DEMO. Cash source remains reported native ledger data within DEMO namespace, not a live account balance. Privacy window explicitly says local simulation/no externalAI. Frontend is production-built software but CompoundOS business environment is TEST, not production deployment.

Rollback: stop only this Compose project, preserve volumes, use original RC worktree. No real data rollback needed. LIVE financial arithmetic/rules/approval behavior unchanged with flagoff; added data_mode field is additive. No remote CI claimed for this local branch. Do not export/copy Preview database into production; LIVE startup/source identity protections reject its namespace/data.


Preview navigation maps Portfolio/Guardian/Committee to the actual native-ledger and candidate governance sections in Investment Workspace. Legacy manual-snapshot Portfolio and user-created Guardian Check screens are not the same ledger and would show empty snapshot/check records; no artificial duplicate ledger was seeded. LIVE navigation remains unchanged. Preview-only Journal read adapter maps current API items/snapshots/audit-events to existing UI types, takes Policy version from real confirmation Audit metadata, and never fabricates a snapshot ID. Backend API/financial records are unchanged.
