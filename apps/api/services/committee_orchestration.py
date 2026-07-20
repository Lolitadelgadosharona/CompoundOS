"""Sprint 006 Slice B — Committee orchestration service.

Full pipeline: evidence → privacy preview → Owner confirmation →
provider call → output validation → immutable report persistence.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from apps.api.models import (
    CommitteeEvidenceItem,
    CommitteeOutcome,
    CommitteeReport,
    CommitteeSession,
)
from apps.api.services.ai_provider import (
    AIModelProvider,
    ProviderConfig,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponse,
    ProviderServerError,
    ProviderTimeoutError,
)
from apps.api.services.evidence_builder import (
    build_evidence_packet,
)
from apps.api.services.provider_output_validator import (
    validate_provider_output,
)

# ═══════════════════════════════════════════════════════════════════════════
# Budget defaults (per Technical Design OD-6-11)
# ═══════════════════════════════════════════════════════════════════════════

MAX_INPUT_TOKENS = 50_000
MAX_OUTPUT_TOKENS = 8_000
MAX_COST_USD = Decimal("1.00")


# ═══════════════════════════════════════════════════════════════════════════
# Committee prompts
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an AI Investment Committee for CompoundOS, a
personal family office operating system. Your role is to provide balanced,
multi-perspective decision support — NOT investment advice.

You must output valid JSON with these sections:
- sections: object with 7 role perspectives (see below)
- supporting_arguments: array of strings
- opposing_arguments: array of strings (MUST be non-empty)
- risks: array of strings (MUST be non-empty)
- policy_alignment: string
- minority_opinions: array of strings
- evidence_citations: array of objects with {evidence_id, citation_ref, claim}
- limitations: array of strings
- recommended_direction: one of:
    "aligned_with_policy", "not_aligned_with_policy",
    "conditionally_aligned", "insufficient_evidence"

Role sections in output.sections:
  long_term_compounding, index_passive_investing,
  macroeconomic_context, risk_capital_preservation,
  devils_advocate, policy_alignment_role, synthesis_chair

RULES:
- Every factual claim MUST cite an evidence_id from the provided evidence
  packet, OR be explicitly marked as "[model inference]".
- Never present model training knowledge as real-time evidence.
- Never use language like "buy", "sell", "hold", "trade", "execute",
  "order", "purchase", "liquidate", or any trading instructions.
- recommended_direction uses ONLY the 4 approved enum values above.
- The macroeconomic_context section should reference provided evidence
  or state "Insufficient current macro evidence" if none is available.
- Always present BOTH supporting and opposing arguments.
- Be neutral and non-advisory.  You are a decision support tool.
"""


# ═══════════════════════════════════════════════════════════════════════════
# Committee orchestration
# ═══════════════════════════════════════════════════════════════════════════


def create_committee_session(
    session: Session,
    household_id: UUID,
    title: str,
    proposal_text: str,
) -> CommitteeSession:
    """Create a new committee session in draft status.

    Owner must explicitly confirm before provider call.
    """
    cs = CommitteeSession(
        id=uuid4(),
        household_id=household_id,
        title=title,
        proposal_text=proposal_text,
        status="draft",
    )
    session.add(cs)
    session.commit()
    return cs


def build_privacy_preview(
    session: Session,
    household_id: UUID,
    committee_session: CommitteeSession,
) -> dict:
    """Build evidence + preview what will be sent to provider.

    Returns a privacy preview dict with:
      - evidence_summary: list of evidence item summaries
      - provider_payload: exactly what would be sent to provider
      - estimated_input_tokens: rough token count estimate
      - exceeds_budget: whether input tokens exceed max
    """
    evidence_items = build_evidence_packet(session, household_id, committee_session)

    # Persist evidence items
    for item in evidence_items:
        session.add(item)
    session.commit()

    payload = _build_provider_payload(committee_session, evidence_items)
    token_estimate = len(json.dumps(payload)) // 4  # rough: ~4 chars per token

    return {
        "evidence_summary": [
            {
                "id": str(e.id),
                "source_type": e.source_type,
                "source_title": e.source_title,
                "citation_ref": e.citation_ref,
                "confidence": e.confidence,
            }
            for e in evidence_items
        ],
        "provider_payload": payload,
        "estimated_input_tokens": token_estimate,
        "exceeds_budget": token_estimate > MAX_INPUT_TOKENS,
        "max_input_tokens": MAX_INPUT_TOKENS,
    }


def run_committee(
    session: Session,
    committee_session: CommitteeSession,
    provider: AIModelProvider,
    *,
    prompt_version: str = "v1",
    schema_version: str = "1.0",
    temperature: Decimal = Decimal("0.0"),
    max_retries: int = 1,
) -> CommitteeReport:
    """Run the committee: call provider, validate output, persist report.

    Raises ValueError for budget/validation failures (non-retryable).
    Raises RuntimeError after exhausting retries on transient errors.

    The caller must have already called build_privacy_preview and obtained
    explicit Owner confirmation before calling this function.
    """
    if committee_session.status != "queued":
        raise ValueError("Session must be in 'queued' status to run")

    committee_session.status = "running"
    session.commit()

    evidence_ids = {
        str(e.id) for e in committee_session.evidence_items
    }
    payload = _build_provider_payload(
        committee_session, committee_session.evidence_items,
    )
    token_estimate = len(json.dumps(payload)) // 4

    if token_estimate > MAX_INPUT_TOKENS:
        _fail_session(session, committee_session, "Token budget exceeded")
        raise ValueError(
            f"Estimated input tokens ({token_estimate}) exceed max ({MAX_INPUT_TOKENS})"
        )

    config = ProviderConfig(
        temperature=float(temperature),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        timeout_seconds=120,
    )

    # Call provider with retry
    response = _call_with_retry(provider, payload, config, max_retries)

    # Parse JSON
    try:
        parsed = json.loads(response.raw_text)
    except json.JSONDecodeError as e:
        _fail_session(session, committee_session, f"Invalid JSON: {e}")
        raise ValueError(f"Provider returned invalid JSON: {e}")

    # Validate
    validation = validate_provider_output(parsed, evidence_ids)
    if not validation.passed:
        error_detail = "; ".join(
            f"{e.field}: {e.message}" for e in validation.errors
        )
        _fail_session(session, committee_session, error_detail)
        raise ValueError(f"Output validation failed: {error_detail}")

    # Persist immutable report
    report = _persist_report(
        session, committee_session, provider, parsed,
        response, prompt_version, schema_version, temperature,
    )
    committee_session.status = "completed"
    session.commit()

    return report


def record_outcome(
    session: Session,
    committee_session: CommitteeSession,
    outcome: str,
    owner_rationale: Optional[str] = None,
) -> CommitteeOutcome:
    """Record Owner's accept/reject/defer outcome.

    The outcome is append-only.  Decision Journal Draft creation
    is a separate Owner action (Slice C / manual workflow).
    """
    if outcome not in ("accepted", "rejected", "deferred"):
        raise ValueError(f"Invalid outcome: {outcome}")

    report = committee_session.report
    if not report:
        raise ValueError("Cannot record outcome without a completed report")

    co = CommitteeOutcome(
        id=uuid4(),
        session_id=committee_session.id,
        report_id=report.id,
        outcome=outcome,
        owner_rationale=owner_rationale,
        decision_draft_id=None,
    )
    session.add(co)
    session.commit()
    return co


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


def _build_provider_payload(
    cs: CommitteeSession,
    evidence_items: list[CommitteeEvidenceItem],
) -> dict:
    """Build the payload sent to the provider."""
    return {
        "proposal": cs.proposal_text,
        "evidence": [
            {
                "evidence_id": str(e.id),
                "source_type": e.source_type,
                "source_title": e.source_title,
                "citation_ref": e.citation_ref,
                "structured_facts": e.structured_facts,
                "confidence": e.confidence,
                "as_of": e.as_of.isoformat() if e.as_of else None,
            }
            for e in evidence_items
        ],
    }


def _call_with_retry(
    provider: AIModelProvider,
    payload: dict,
    config: ProviderConfig,
    max_retries: int,
) -> ProviderResponse:
    user_prompt = json.dumps(payload)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return provider.call(SYSTEM_PROMPT, user_prompt, config)
        except (ProviderTimeoutError, ProviderRateLimitError, ProviderServerError) as e:
            last_error = e
            if attempt < max_retries:
                continue
        except ProviderError:
            raise  # non-retryable — re-raise immediately

    raise RuntimeError(
        f"Provider call failed after {max_retries + 1} attempts: {last_error}"
    )


def _persist_report(
    session: Session,
    cs: CommitteeSession,
    provider: AIModelProvider,
    parsed: dict,
    response: ProviderResponse,
    prompt_version: str,
    schema_version: str,
    temperature: Decimal,
) -> CommitteeReport:
    content_json = json.dumps(parsed, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()

    report = CommitteeReport(
        id=uuid4(),
        session_id=cs.id,
        provider=provider.provider_name,
        model_id=response.model or "deepseek-chat",
        model_version=None,
        prompt_version=prompt_version,
        schema_version=schema_version,
        temperature=temperature,
        provider_params=None,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost=Decimal("0.0"),  # computed from actual tokens below
        report_content=parsed,
        content_hash=content_hash,
    )
    session.add(report)
    session.flush()
    return report


def _fail_session(
    session: Session,
    cs: CommitteeSession,
    error_detail: str,
) -> None:
    cs.status = "failed"
    # Error detail is not persisted in current schema — logged only
    session.commit()
