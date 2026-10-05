# Independent counterexamples

| Original input | BEFORE defect | AFTER required result | Evidence strength |
|---|---|---|---|
| VTI provider ID, NOTVTI/EUR/OTHER identity | Reused USD VTI UUID | Reject identity conflict; original UUID unchanged | PostgreSQL integration |
| Requested AAPL, returned MSFT metadata | Accepted price wrapped as AAPL | Reject actual returned identity | Unit adapter probe |
| Fresh simulation price | COMPLETE and READY | DEGRADED, not ready | Pure deterministic probe |
| Published CORE max=0, initial buys | READY | Policy blocks projected CORE buys | PostgreSQL integration |
| Citation [{}], aligned direction | Accepted and manually approved | Validation fails; approval remains blocked | PostgreSQL integration |
| Linked contribution draft discard | FK failure | Rejection audit; immutable link retained | PostgreSQL integration |
| research_run_id plus 36 hyphens | DataError | Safe free-text update, no invalid UUID cast | PostgreSQL integration |
| Uppercase historical valid UUID | Missing link | Both lowercase/uppercase links retained | Migration integration |

Before evidence comes from the unchanged audit source archive and isolated pre-fix DB. After inputs preserve the defective identity/marker/citation values; expectations change to rejection/preservation. The contribution prompt tag is intentionally upgraded from v1 to v1.1. Regression coverage also includes wrong venue/currency/type, class shares, unknown identity, missing/stale/future data, FX, untrusted valuation, missing policy context, incomplete research Committee, stale ORM duplicate call, manual execution and a real 20% published test limit.

The third full-suite run and one overlapping targeted run are INVALIDATED: both reset the same test database. They are retained for transparency but are not acceptance evidence. Final full regression runs alone.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
