2026-10-05 · VERIFIED FACT / INFERENCE / RECOMMENDATION / OPEN QUESTION are distinguished below. No production deployment, production migration, merge, broker connection or trade is authorized.

# V1 Release Candidate

VERIFIED FACT: release branch `codex/compoundos-v1-release-candidate` preserves all seven original hardening commits through `5639a22d67ede82b5a60b4d02906c5e1a99cef4e` by ancestry. Hardening base is `1b3a979fbd328062d8293e67bbddb72eeb60cddc`; main/PR base was `20ceca579b9678c17a1122e2d9b9873812f7fa55`. The Owner package's patch/source archive was compared to actual Git objects and all package hashes verified. No unrelated features, binary/generated artifacts or credential-pattern matches were found in the seven-commit delta. Pattern scanning cannot prove the absence of every possible secret.

A separate RC PR is used to preserve #120, its original branch/worktree and its earlier audit. No force-push, rebase or cherry-pick rewrites the verified history. The RC supersedes #120 for review; #120 must not be merged as-is. Exact final HEAD, PR URL/number, fresh CI and commit list are recorded in `outputs/COMPOUNDOS_V1_RELEASE_CANDIDATE_REPORT.md` and its evidence manifest, outside Git to avoid a self-referential SHA.

Narrow release delta: current DeepSeek model configuration/non-thinking JSON payload, two release acceptance tests, two test import-order lint fixes and these eleven documents. DeepSeek's actual model identity remains provider-reported. No pricing is invented or credentials installed. No additional schema migration is introduced by RC.

Baseline evidence: backend1594/frontend259; final RC must rerun full suites, lint, types, production builds and audits against its exact SHA. Historical deployed SHA remains UNKNOWN. Technical code readiness and production authorization/real-provider readiness are separate conclusions. Owner review and current CI are prerequisites to a merge decision.
