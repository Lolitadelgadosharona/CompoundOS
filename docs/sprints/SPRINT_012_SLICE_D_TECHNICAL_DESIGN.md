# Sprint 012 Slice D — Technical Design
# AI Governance Layer

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 012 Slice A (LLM Runtime): DONE (59d137e)
> Sprint 012 Slice B (Pipeline): DONE (b5444ac)
> Sprint 012 Slice C (Tool Foundation): DONE (1d73f84)
> Sprint 012 Slice D: DESIGN ONLY

---

## 1. Objective

Slice D enforces the AI governance boundaries that have been defined
since Sprint 010. While prior slices built capability (LLM runtime,
execution pipeline, tool interfaces), Slice D builds the **guardrails**
that ensure AI never exceeds its advisory mandate.

---

## 2. AI Action Permission Enforcement

### 2.1 Permission Matrix (from OD-12-5)

| # | Action | Classification | Enforcement |
|---|---|---|---|
| 1 | Fetch market data | AUTO | ResearchPipeline calls EvidenceCollector |
| 2 | Load portfolio data | AUTO | EvidenceCollector reads positions/accounts |
| 3 | Load policy/guardian data | AUTO | EvidenceCollector reads policy_rules/guardian_events |
| 4 | Execute LLM perspective calls | AUTO | PerspectiveExecutor calls LLM provider |
| 5 | Generate investment memo | AUTO | ResearchPipeline._generate_memo |
| 6 | Calculate confidence score | AUTO | ConfidenceEngine.calculate |
| 7 | Store completed analysis | AUTO | PerspectiveExecutor._store_analysis |
| 8 | Log execution metrics | AUTO | PerspectiveExecutor._log_xxx writes llm_execution_log |
| 9 | Create investment idea | OWNER | POST /api/ideas (existing, Sprint 009-C) |
| 10 | Request committee review | OWNER | POST /api/ideas/{id}/request-review (existing) |
| 11 | Approve investment | OWNER | Decision creation (existing) |
| 12 | Start research execution | OWNER | POST /api/research/start (Sprint 012-B) |
| 13 | Modify policy | NEVER | Trigger-blocked (existing) |
| 14 | Execute trade | NEVER | No code path exists |
| 15 | Connect to broker | NEVER | No code path exists |

### 2.2 Enforcement Architecture

```python
class PermissionGate:
    """Central enforcement point for AI action permissions."""

    AUTO_ACTIONS = frozenset({
        "fetch_market_data", "load_portfolio_data",
        "load_policy_data", "load_guardian_data",
        "execute_llm_call", "generate_memo",
        "calculate_confidence", "log_execution",
    })

    OWNER_ACTIONS = frozenset({
        "create_idea", "request_review",
        "approve_investment", "start_research",
    })

    NEVER_ACTIONS = frozenset({
        "modify_policy", "execute_trade", "connect_broker",
    })

    @classmethod
    def check(cls, action: str, caller: str) -> bool:
        if action in cls.NEVER_ACTIONS:
            return False
        if action in cls.OWNER_ACTIONS and caller != "owner":
            return False
        return True
```

### 2.3 Integration Points

| Integration | Mechanism |
|---|---|
| ResearchPipeline | Calls only AUTO actions internally |
| API routers | POST endpoints = OWNER actions (auth middleware enforces) |
| Database triggers | NEVER actions blocked at DB level (existing) |
| EvidenceCollector | Only reads data (AUTO) |

---

## 3. LLM Governance

### 3.1 Prompt Version Enforcement

Every LLM call MUST reference an active prompt template:

```
PerspectiveExecutor._execute_one:
  1. Load prompt_templates WHERE perspective = :p AND status = 'active'
  2. If no active prompt → abort with error "No active prompt for {perspective}"
  3. Record prompt_version in perspective_analyses
  4. Record prompt_version in llm_execution_log
```

**Enforcement**: The executor queries `prompt_templates` before every
LLM call. No hardcoded prompts. No bypassing the template system.

### 3.2 Model Tracking

Every LLM call records:

| Field | Source | Stored In |
|---|---|---|
| `model` | prompt_templates.default_model | perspective_analyses |
| `model_version` | llm_execution_log | llm_execution_log |
| `prompt_version` | prompt_templates.version | both tables |

**Enforcement**: The `llm_execution_log` table (Slice A) already has
`model` and `prompt_template_id` columns. Every execution log row
provides a complete audit of which model and prompt produced which
analysis.

### 3.3 Execution Audit Trail

A complete audit trail for a single perspective:

```
ResearchRun (id=run-1)
  └── llm_execution_log (perspective=value, model=claude-sonnet-4,
                         prompt_template_id=pt-3, prompt_version=2,
                         input_tokens=1500, output_tokens=800,
                         cost_estimate=0.012, status=success)
  └── perspective_analyses (perspective=value, model=claude-sonnet-4,
                            prompt_version=2, analysis={...})
```

**Traceability**: From any perspective_analyses row, follow `run_id` →
research_runs → request_id → committee_review_requests → investment_ideas.
The full chain from idea to specific LLM execution is auditable.

---

## 4. Audit Integration

### 4.1 AI Execution Events

Every AI execution log entry qualifies as an audit event. The
`llm_execution_log` table serves as both execution tracking AND
audit trail:

| Audit Question | Answered By |
|---|---|
| Who initiated? | research_runs → research_requests → committee_review_requests.requested_by |
| What model? | llm_execution_log.model |
| Which prompt version? | llm_execution_log.prompt_template_id |
| When? | llm_execution_log.started_at / completed_at |
| Cost? | llm_execution_log.cost_estimate |
| Result? | llm_execution_log.status |

### 4.2 audit_log Integration (Future)

The existing `audit_log` table (Sprint 010-D) can optionally receive
AI governance events in a future sprint:

```sql
INSERT INTO audit_log (event_type, actor_role, action, resource)
VALUES ('ai.execution.completed', 'ai', 'perspective_analysis',
        'research_run:run-1:perspective:value');
```

Not required for Slice D — `llm_execution_log` provides sufficient
audit detail for V1.

---

## 5. Cost Governance

### 5.1 Token Tracking

Already implemented in `llm_execution_log` (Slice A):

| Column | Purpose |
|---|---|
| `input_tokens` | Tokens sent to LLM |
| `output_tokens` | Tokens received from LLM |
| `cost_estimate` | Calculated cost (model-specific pricing) |
| `cost_currency` | "USD" |

### 5.2 Cost Calculation Formula

Per-model pricing (configurable via environment):

```python
MODEL_PRICING = {
    "anthropic/claude-sonnet-4": {
        "input_per_1k": 0.003,   # $3/M input tokens
        "output_per_1k": 0.015,  # $15/M output tokens
    },
    "openai/gpt-4o": {
        "input_per_1k": 0.0025,
        "output_per_1k": 0.010,
    },
}

def calculate_cost(model: str, input_tokens: int,
                   output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {})
    cost = (
        input_tokens / 1000 * pricing.get("input_per_1k", 0.005)
        + output_tokens / 1000 * pricing.get("output_per_1k", 0.015)
    )
    return round(cost, 6)
```

### 5.3 Budget Threshold Alerts

Not implemented in Slice D. Design for future:

```python
BUDGET_THRESHOLDS = {
    "per_run": 0.50,    # Alert if single run exceeds $0.50
    "per_day": 2.00,    # Alert if daily spend exceeds $2.00
    "per_month": 30.00, # Alert if monthly spend exceeds $30.00
}
```

Alerts would create `notification_events` (existing infrastructure
from Sprint 007/008).

---

## 6. Human Authority Boundary

### 6.1 Explicit Prohibitions

| AI Action | Enforcement Layer |
|---|---|
| Approve investment | Decision creation requires Owner POST (API auth) |
| Modify policy | Policy tables have immutability triggers (Sprint 002) |
| Execute trade | No `trade`/`order` code paths exist anywhere |
| Create owner decisions | Decision creation endpoint = OWNER_MUTATION |
| Modify audit log | audit_log has immutability trigger (Sprint 010-D) |
| Change prompt templates | prompt_templates immutable when active (Sprint 012-A) |

### 6.2 Defense in Depth

| Layer | Mechanism |
|---|---|
| API | Global auth middleware → Owner-only mutations require X-API-Key |
| Service | PermissionGate.check() called before every AI action |
| Database | CHECK + trigger constraints prevent forbidden modifications |
| Audit | llm_execution_log + audit_log provide immutable evidence |

---

## 7. Database Impact

No new tables or columns. Slice D is a governance enforcement layer
that operates on existing infrastructure:

| Existing Table | Used For |
|---|---|
| `llm_execution_log` | Audit trail, cost tracking |
| `prompt_templates` | Version enforcement |
| `audit_log` | Future governance events (optional) |

---

## 8. API Impact

No new API endpoints. Governance is enforced internally at the
service layer.

---

## 9. Security

| Constraint | Enforcement |
|---|---|
| No credentials | API keys in environment variables only |
| No broker integration | No broker code paths |
| No trading capability | No trade methods |
| AI cannot override Owner | PermissionGate + API auth middleware |

---

## 10. Estimate

| Component | Lines | Tests |
|---|---|---|
| PermissionGate class | ~50 | 5 |
| Prompt version enforcement | ~30 | 3 |
| Cost calculation service | ~50 | 4 |
| Governance integration tests | — | ~6 |
| **Total** | **~130** | **~18** |

---

## 11. Owner Decisions

See `docs/sprints/SPRINT_012_SLICE_D_OWNER_DECISIONS.md` (4 pending).
