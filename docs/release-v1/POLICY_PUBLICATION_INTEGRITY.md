# Policy publication integrity — narrow launch-blocker repair

VERIFIED FACT: current RC11477dc cloned text/allocations but omitted existing policy_capital_buckets/policy_rules when cloning a published version or publishing the draft. Draft deletion then removed those rows. This can silently remove tighter bounds/critical rules, so it is a genuine financial-governance defect, not optional cleanup. Three counterexamples against an isolated pristine11477dc archive fail: exact draft snapshot, current-version clone and Personal setup publication.

Fix: copy existing bucket name/target/min/max/description/order and rule type/value/severity/enabled/description/order within the same existing transaction. Version snapshots are copied before sealing and draft deletion; source versions retain their payload. Fresh row IDs/parent links identify the new version/draft, while original version history is unchanged except normal superseded status/time. Both publication entry points use the same helper.

No rule values are changed/interpreted, no default concentration threshold is loosened, no new Policy lifecycle/API/UI or schema migration is added. Unknown enabled rules remain fail-closed. Three regressions cover the actual service lifecycle and retain disabled/custom flags. Full final tests and actual final staging source SHA are in the final Owner report.

The fresh synthetic staging Policy uses explicit20%/0% limits identical to its original test notes via standard draft/publish lifecycle, with original v1 payload retained. Existing real Owner Policy is not read or changed. This repair prevents loss of supplied constraints; it does not invent missing rules or reinterpret historical notes. Actual production Policy/data baseline still requires Owner review.
