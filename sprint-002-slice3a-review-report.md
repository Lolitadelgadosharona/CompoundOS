# CompoundOS Sprint 002 Slice 3A Independent Review Report

**Reviewer**: Independent Review Agent
**Date**: 2026-07-16
**PR**: #11
**Branch**: sprint/002-decision-persistence
**HEAD**: 7f455ec8aac700e9da76ccda91db0114caaaa223

---

## Executive Summary

**Conclusion**: REQUEST CHANGES

**Findings**:
- BLOCKER: 1
- HIGH: 0
- MEDIUM: 0
- LOW: 0
- NON-BLOCKING: 0

---

## BLOCKER Findings

### B1: Deferred Trigger Coverage Gap - UPDATE and Child Table Mutations Can Bypass Consistency Check

**Severity**: BLOCKER

**Location**: 
- `migrations/versions/0003_decision_journal_foundation.py` lines 672-676
- Trigger: `trg_decision_lifecycle_consistency`

**Current Implementation**:
```sql
CREATE CONSTRAINT TRIGGER trg_decision_lifecycle_consistency
AFTER INSERT ON public.decisions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.fn_decision_lifecycle_consistency()
```

**Problem**:
The deferred consistency trigger only fires on `INSERT ON decisions`. This creates multiple bypass scenarios where lifecycle invariants can be violated:

#### Bypass Scenario 1: UPDATE existing draft to confirmed without snapshot
1. Previous transaction: INSERT decision (status='draft'), INSERT draft, COMMIT
2. Current transaction: UPDATE decisions SET status='confirmed' (no snapshot created)
3. BEFORE UPDATE trigger allows the transition (draft→confirmed is valid)
4. Deferred trigger does NOT fire (no INSERT in current transaction)
5. **Result**: status='confirmed' with no snapshot - VIOLATES INVARIANT

#### Bypass Scenario 2: DELETE draft from existing draft decision
1. Previous transaction: INSERT decision (status='draft'), INSERT draft, COMMIT
2. Current transaction: DELETE FROM decision_drafts WHERE decision_id = X
3. Deferred trigger does NOT fire (no INSERT on decisions)
4. **Result**: status='draft' with no draft row - VIOLATES INVARIANT

#### Bypass Scenario 3: INSERT snapshot for existing draft decision
1. Previous transaction: INSERT decision (status='draft'), INSERT draft, COMMIT
2. Current transaction: INSERT decision_confirmed_snapshots (for draft decision)
3. Deferred trigger does NOT fire (no INSERT on decisions)
4. **Result**: status='draft' with snapshot - VIOLATES INVARIANT

#### Bypass Scenario 4: INSERT draft for existing confirmed decision
1. Previous transaction: INSERT decision, INSERT draft, INSERT snapshot, UPDATE status='confirmed', COMMIT
2. Current transaction: INSERT decision_drafts (for confirmed decision)
3. Deferred trigger does NOT fire (no INSERT on decisions)
4. **Result**: status='confirmed' with draft - VIOLATES INVARIANT

**Root Cause**:
The technical design (Section 6) specifies a deferred constraint trigger but does not explicitly list all required trigger events. The implementation only covers INSERT on decisions, missing UPDATE and child table mutations.

**Required Fix**:
Add deferred constraint triggers on all events that can change the decision/draft/snapshot combination:

1. `decisions AFTER INSERT OR UPDATE` - catch new decisions and status changes
2. `decision_drafts AFTER INSERT OR DELETE` - catch draft creation and deletion
3. `decision_confirmed_snapshots AFTER INSERT OR DELETE` - catch snapshot creation and deletion

All triggers should call the same `fn_decision_lifecycle_consistency()` function, but child table triggers need to extract `decision_id` from `NEW` (for INSERT) or `OLD` (for DELETE).

**Test Coverage Gap**:
Current tests only verify scenarios where the Decision is INSERTed in the same transaction. No tests verify bypass scenarios where the Decision exists from a previous transaction.

**Impact**:
This is a critical correctness issue. The deferred trigger is the last line of defense for lifecycle invariants. If it can be bypassed, the database cannot guarantee:
- Every confirmed/archived decision has exactly one snapshot
- No draft decision has a snapshot
- No decision has both draft and snapshot

This violates the core design principle of database-level enforcement over service-level validation.

---

## Detailed Analysis

### A. Deferred Lifecycle Consistency Trigger

**Status**: FAILS - Coverage gap identified above (BLOCKER B1)

### B-K. Other Areas

**Status**: PASS - All other aspects (BEFORE triggers, immutability, DELETE guard, correction validation, ORM parity, test quality) are well-implemented.

---

## Conclusion

**REQUEST CHANGES**

The implementation has one critical BLOCKER: the deferred consistency trigger can be bypassed by UPDATE-only or child-table-only mutations when the Decision exists from a previous transaction.

**Next step**: Fixer addresses BLOCKER B1, then Final Verifier performs independent re-review.
