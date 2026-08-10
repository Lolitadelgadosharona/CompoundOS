# Sprint 013 Slice D — Technical Design
# Investment Committee Decision Lifecycle

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 013 Slice A (LLM Runtime): DONE (82bb43e, PR #94)
> Sprint 013 Slice B (Evidence Layer): DONE (4fe15ea, PR #95)
> Sprint 013 Slice C (Intelligence Loop): DONE (f7c46ef, PR #96)
> Sprint 013 Slice D: DESIGN ONLY

---

## 1. Objective

Slice D completes the full investment decision lifecycle. Slice C
produces investment memos with confidence scores. Slice D connects
those memos to committee review, Owner decision, journal entry, and
long-term learning — closing the loop from AI analysis to real-world
outcome tracking.

---

## 2. Architecture — Complete Lifecycle

```
Research Intelligence Pipeline (Slice C)
        │
        ▼
Investment Memo (investment_memos)
        │
        ▼
Committee Review Integration (Slice D — NEW)
        │
        ├── committee_bridge connects memo to session
        ├── Evidence summary presented to committee
        └── Committee recommendation recorded
        │
        ▼
Owner Decision (Slice D — NEW)
        │
        ├── Approve / Reject / Modify
        ├── Recorded in decision_journal
        └── Action logged to audit_log
        │
        ▼
Decision Journal (Sprint 009-C, existing)
        │
        ├── Original thesis stored
        ├── Evidence snapshot referenced
        ├── Confidence score recorded
        └── Owner action preserved
        │
        ▼
Learning Loop (Slice D — NEW integration)
        │
        ├── Outcome review scheduled (30d/90d/1yr)
        ├── Actual performance compared to prediction
        ├── prediction_accuracy updated
        └── knowledge_memory enriched
```

---

## 3. Committee Review Integration

### 3.1 Flow

```
InvestmentMemo (Slice C output)
        │
        ▼
MemoGenerator generates memo → investment_memos row
        │
        ▼
POST /api/research/complete (NEW or enhanced)
        │
        ├── Links memo to committee_review_requests
        ├── Creates committee session (or finds existing)
        └── Populates committee_evidence_items with:
            ├── Market data snapshot
            ├── 6 perspective analyses
            ├── Memo summary
            └── Confidence report
        │
        ▼
Committee reviews (existing Sprint 010-A flow)
        ├── Committee members (Owner + AI perspectives)
        ├── Each perspective votes: BUY/HOLD/PASS
        └── Committee bridge stores outcome
```

### 3.2 Bridge Mapping

| Sprint 010-A Concept | Sprint 013-D Implementation |
|---|---|
| `committee_review_requests` | Created when research run completes |
| `committee_sessions` | Each research run → one session |
| `committee_evidence_items` | Market data, analyses, memo as evidence |
| `committee_reports` | Synthesis of perspectives into report |
| `committee_outcomes` | Final vote + recommendation |

---

## 4. Owner Authority

### 4.1 Permission Boundaries

| Action | Classification | Enforced By |
|---|---|---|
| Generate memo | AUTO | PermissionGate |
| Calculate confidence | AUTO | ConfidenceEngine |
| Present to committee | AUTO | Committee bridge |
| Committee vote (AI perspective) | AUTO | PermissionGate |
| **Approve investment** | **OWNER** | API auth + PermissionGate |
| **Reject investment** | **OWNER** | API auth + PermissionGate |
| **Modify decision** | **OWNER** | API auth + PermissionGate |
| Execute trade | NEVER | PermissionGate |
| Modify policy | NEVER | PermissionGate + triggers |

### 4.2 Owner Decision Flow

```
Committee recommendation presented
        │
        ▼
Owner reviews:
  ├── Investment Memo (11 sections)
  ├── Committee votes (6 perspectives)
  ├── Confidence score
  └── Guardian status
        │
        ▼
Owner action: APPROVE / REJECT / MODIFY
        │
        ├── APPROVE → decision recorded, status = confirmed
        ├── REJECT  → decision recorded, status = rejected
        └── MODIFY  → decision recorded with notes, status = modified
        │
        ▼
Decision Journal entry created
Audit log entry created
```

---

## 5. Decision Journal Integration

### 5.1 Schema (existing from Sprint 009-C)

`decision_confirmed_snapshots` table already stores:
- `investment_idea_id` — which idea
- `decision_type` — BUY/HOLD/PASS
- `rationale` — Owner reasoning
- `confidence_at_decision` — confidence score at decision time
- `decision_by` — "owner"

### 5.2 Slice D Enhancement

Link memo to decision:
- `investment_memos.id` referenced from decision
- Evidence snapshot preserved at decision time
- Committee votes recorded

```python
# When Owner approves:
session.execute(text(
    "INSERT INTO decision_confirmed_snapshots"
    " (id, investment_idea_id, decision_type, rationale,"
    " confidence_at_decision, decision_by, memo_id,"
    " committee_session_id)"
    " VALUES (:id, :idea, :dt, :r, :conf, 'owner',"
    " :memo, :session)"
))
```

---

## 6. Learning Loop

### 6.1 Outcome Review Scheduling

From Sprint 010-C (Learning Loop design):
- High-impact decisions (≥5% impact): auto-schedule 30d/90d/1yr reviews
- Low-impact: manual review only
- `decision_reviews` table tracks review status

### 6.2 Prediction Accuracy

When a decision review completes and outcomes are known:

```python
# Compare prediction vs actual:
actual_return = outcome.get("return_pct", 0)
predicted_confidence = decision.confidence_at_decision

# Update knowledge memory:
UPDATE investment_knowledge_memory
SET prediction_accuracy = jsonb_build_object(
    'predicted', predicted_confidence,
    'actual', actual_return,
    'review_date', NOW()
)
WHERE entity_key = :symbol
```

### 6.3 Confidence Calibration

Track prediction accuracy over time:
- If predictions consistently over-confident → calibrate ConfidenceEngine weights
- This is a retrospective analysis, not Slice D scope (future sprint)

### 6.4 Knowledge Enrichment

After decision:
- Store thesis + outcome in `investment_knowledge_memory`
- Associate with entity
- Make available for future research via `DatabaseKnowledgeProvider` (Slice B)

---

## 7. Provenance Chain

```
Decision (decision_confirmed_snapshots)
  ├── memo_id → investment_memos
  │     ├── run_id → research_runs
  │     │     └── request_id → research_requests
  │     │           └── review_request_id → committee_review_requests
  │     ├── perspectives (via committee_evidence_items)
  │     │     └── run_id → perspective_analyses
  │     │           ├── model, prompt_version, conviction_score
  │     │           └── run_id → llm_execution_log
  │     │                 ├── model, tokens, cost, duration
  │     │                 └── prompt_template_id → prompt_templates
  │     └── confidence → ConfidenceEngine MODEL_VERSION
  │
  ├── committee_session_id → committee_sessions
  │     └── outcomes → committee_outcomes
  │
  └── evidence → committee_evidence_items
        └── source type, content, retrieved_at
```

Every decision traces back through the full chain to the original
market data, LLM execution, and research request.

---

## 8. Database Impact

**No new tables.** Slice D uses existing schema:

| Table | Slice D Usage |
|---|---|
| `investment_memos` | Read memo + confidence |
| `committee_review_requests` | Create when research completes |
| `committee_sessions` | Create one per research run |
| `committee_evidence_items` | Store evidence snapshot |
| `committee_outcomes` | Record committee recommendation |
| `decision_confirmed_snapshots` | Write Owner decision |
| `decision_reviews` | Schedule outcome reviews |
| `investment_knowledge_memory` | Update prediction_accuracy |
| `audit_log` | Log Owner decision event |

---

## 9. API Impact

| Method | Path | Classification | Purpose |
|---|---|---|---|
| POST | /api/research/{id}/complete | OWNER_MUTATION | Link memo to committee, create session |
| POST | /api/decisions/{id}/approve | OWNER_MUTATION | Owner approves committee recommendation |
| POST | /api/decisions/{id}/reject | OWNER_MUTATION | Owner rejects recommendation |
| GET | /api/decisions/{id}/provenance | READ | Full provenance chain from decision |

Existing `POST /api/research/start` triggers Slice C pipeline.
New `/complete` endpoint bridges to committee.

---

## 10. Security

| Constraint | Enforcement |
|---|---|
| No broker integration | No broker code paths |
| No trading | No trade methods |
| No credentials | Env vars only (existing) |
| AI cannot approve | PermissionGate + API auth |
| AI cannot modify policy | PermissionGate + triggers |
| AI cannot execute trades | NEVER actions in ActionMatrix |

---

## 11. Test Strategy

| Test Area | Count |
|---|---|
| Committee bridge: memo → session | 3 |
| Owner decision: approve/reject/modify | 3 |
| Decision journal: memo linkage | 2 |
| Learning loop: prediction_accuracy | 3 |
| Provenance chain | 2 |
| Authority boundary | 1 |
| Graceful degradation | 2 |
| **Total** | **~16** |

---

## 12. Dependencies

Slice D depends on all prior Sprint 013 components plus:
- Committee bridge (Sprint 010-A)
- Decision journal (Sprint 009-C)
- Learning loop design (Sprint 010-C)
- Guardian (Sprint 010-B)
- Auth (Sprint 010-D)

---

## 13. Estimate

| Component | Lines | Tests |
|---|---|---|
| Committee integration service | ~80 | 3 |
| Decision endpoint | ~60 | 3 |
| Learning loop integration | ~80 | 3 |
| Provenance service | ~60 | 2 |
| Pipeline completion handler | ~60 | 3 |
| Authority | ~10 | 1 |
| **Total** | **~350** | **~15** |

---

## 14. Owner Decisions

**No new Owner Decisions required.** All architecture decisions are
resolved by prior approvals:
- OD-13-7: Human approval boundary (Owner decides)
- OD-12-5: AI action permission matrix
- Sprint 010 ODs: Committee bridge, learning loop design

---

## 15. Acceptance Criteria

Slice D is successful when:

1. A completed research memo enters committee review
2. Committee evidence items are populated from the memo and perspectives
3. Owner can approve/reject/modify with full provenance
4. Decision is journaled with memo + confidence + committee recommendation
5. Learning loop schedules outcome reviews
6. Prediction accuracy is updated when outcomes are known
7. AI never approves, trades, or modifies policy
