# Effective published Policy

VERIFIED FACT: Existing published capital bucket semantics are positions-only percentage weights, Decimal arithmetic rounded to .01 percent, with the existing min/max bounds. `effective_policy` shares published bucket retrieval and evaluation between projected contribution checks and descriptive Guardian checks; the reviewed evidence carries Policy version, bounds, funding account and findings. Approval re-evaluates that same evidence.

Projected buys use the actual selected owned funding account and its capital bucket. Multi-account ambiguity fails closed; no CORE default is invented. The account must use the plan base currency. Initial budget cannot borrow cash from another account. Monthly CNY contribution is converted with verified FX and remains a proposal; it does not write actual cash or positions.

Legacy setup notes containing maximum-position/minimum-cash limits must agree with explicit enabled rules; otherwise LEGACY_POLICY_LIMIT_RECONCILIATION_REQUIRED blocks the proposal. This avoids choosing a precedence or rewriting a historical Policy. Unknown published rules, unknown custom rule structures, missing required account bucket or unsupported Policy prose block approval rather than being treated as compliant. Existing numeric rules and Guardian severity remain unchanged. Prose-heavy legacy setup requires Owner publication of explicit evaluable constraints; historical Policy is not rewritten.

Synthetic scenario verifies USD100,000 initial capital, CNY10,000 monthly contribution, VTI/QQQ/VXUS/SGOV as examples, contribution-first purchases, no SELL, drift and conservation. Its compliant fixture explicitly publishes a 60% maximum solely in the isolated test DB. A separate fixture publishes 20% and proves the illustrative concentrated plan is blocked. No Owner threshold is increased.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.

OPEN QUESTION for Owner: how to publish/reconcile limits carried only in historical setup notes. This sprint deliberately blocks inconsistent or absent explicit rules; it does not perform a Policy-data migration.
