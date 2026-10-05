# Dependency/security results

VERIFIED FACT: npm production audit has zero vulnerabilities. Python direct requirements and production deployment lock audit have zero known vulnerabilities. No production dependency version was weakened or forcibly auto-fixed.

All-dependency npm audit still reports five high nodes for one unpatched braces denial-of-service advisory through eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces 3.0.3. It is a development lint chain, absent from the production audit. Exploit requires a deeply nested brace pattern to reach those walkers, potentially from untrusted project inputs/paths during local/CI lint. Keep untrusted lint input isolated; no server runtime exposure was demonstrated.

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists affected <=3.0.3 and no patched version as checked on 2026-10-05. npm suggests a major downgrade to eslint-config-next 14.2.35, which conflicts with the retained Next16 stack. That destabilizing workaround is deferred under the Owner's explicit dev-risk instruction. ESLint maintenance risk remains non-blocking and separately tracked.

No new external network destination, broker, telemetry or credential file is introduced. Yahoo's production safety switch remains fail closed outside explicit development/test or authorization configuration. COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED is not a license. Actual production use, quote/FX/history retention, redistribution and evidence-storage permissions remain NOT VERIFIED and block launch.

These are dependency audits, not proof of an exhaustive penetration test. Existing auth/permission regressions are covered by the final backend/frontend suites. Synthetic provider values are confined to test fixtures; production cannot trust adapters marked test_only.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
