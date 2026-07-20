# Sprint 007 — Open Questions

> **15 OWNER DECISIONS — ALL RESOLVED (2026-07-20). Implementation Not Authorized.**
>
> See `SPRINT_007_TECHNICAL_DESIGN.md` for the resolved design,
> architecture, and safety boundaries.  All slices require separate
> explicit Owner authorization.

| ID | Question | Option | Status |
|----|----------|--------|--------|
| OD-7-1  | Sprint 007 scope | **A**: Hardening + selective local Notification | Owner Decided |
| OD-7-2  | Backup automation | **B**: explicit opt-in macOS launchd + manual CLI. No Hermes cron. | Owner Decided |
| OD-7-3  | Backup retention | **A**: 7 daily + 4 weekly + 12 monthly. Forbidden to delete last healthy backup. | Owner Decided |
| OD-7-4  | Export formats | **Both**: DR backup = PostgreSQL custom dump + manifest + SHA256. Owner export = JSON + CSV. | Owner Decided |
| OD-7-5  | Notification delivery | **A+B**: macOS Notification Center + internal persisted notifications. No external notification services. | Owner Decided |
| OD-7-6  | Quiet hours | **A**: Default 22:00–08:00. Critical health events may bypass but must deduplicate. | Owner Decided |
| OD-7-7  | Health dashboard | **A**: Component-level, read-only health dashboard. | Owner Decided |
| OD-7-8  | Restore verification | **A+B**: Every backup validated by hash/manifest/pg_restore check. Periodic restore to one-shot `_test` DB. Full PG suite for release gates and restore drills. | Owner Decided |
| OD-7-9  | Startup health check | **A**: API/Worker DB or schema anomalies → fail closed. Frontend degrades to read-only. | Owner Decided |
| OD-7-10 | Notification dedup | **A**: Persisted fingerprint, default dedup 24h window. | Owner Decided |
| OD-7-11 | Export retention | **A**: Server-side export files retained max 24h. | Owner Decided |
| OD-7-12 | Personal V1 completion definition | **Revised**: RPO ≤24h, target RTO ≤2h, restore drill successful, 0 known B/H data-safety issues. | Owner Decided |
| OD-7-13 | Deferred to V2 | **A**: Market Data, Family Goals, external notifications, cloud backup, SaaS, all deferred to V2. | Owner Decided |
| OD-7-14 | Slice ordering | **A**: Slice A (Backup/Restore/Export) → Slice B (Health/Credential) → Slice C (Notification). | Owner Decided |
| OD-7-15 | Backup encryption & destination | **A**: Owner-selected local destination + encrypted backup + age recipient. Private recovery key in Keychain with offline copy required. Fail closed if encryption not configured. Cloud-sync destinations forbidden by default. | Owner Decided |

All 15 decisions block Sprint 007 implementation.  No Slice authorization
until all are resolved per the Technical Design Gate merge.
