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


CONTRIBUTION_PROMPT = (
    SYSTEM_PROMPT
    + """
CONTRIBUTION-V1 CONTRACT:
All quantitative FACTs are exclusively in supplied deterministic evidence.
Never generate or repeat numerical quantities (digits or spelled-out numbers).
Every narrative statement is model inference, never a live financial fact.
Return confidence as exactly low, medium, or high.
Each citation must copy evidence_id, citation_ref and citation_claim EXACTLY
from its supplied registry entry, including simulated/historical labels.
If evidence cannot support alignment, return insufficient_evidence.
"""
)


def prompt_for(version):
    if version == "contribution-v1.1":
        return CONTRIBUTION_PROMPT
    if version == "v1":
        return (
            SYSTEM_PROMPT
            + "\nCopy each supplied citation_claim/ref exactly; do not invent evidence. "
            "Never generate numerical facts; all narrative is model inference."
        )
    raise ValueError("Unsupported Committee prompt version")


def provider_rates(provider):
    import os

    if provider.provider_name != "deepseek":
        if os.getenv("ENVIRONMENT") != "test":
            raise ValueError("Unconfigured production provider")
        return Decimal(0), Decimal(0)
    try:
        rates = tuple(
            Decimal(os.environ[k])
            for k in (
                "COMPOUNDOS_DEEPSEEK_INPUT_USD_PER_MILLION",
                "COMPOUNDOS_DEEPSEEK_OUTPUT_USD_PER_MILLION",
            )
        )
        if any(not x.is_finite() or x <= 0 for x in rates):
            raise ValueError
        return rates
    except (KeyError, ValueError, ArithmeticError) as exc:
        raise ValueError("Provider cost configuration required before production call") from exc


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
    schema_version: str = "hardening-1",
    temperature: Decimal = Decimal("0.0"),
    max_retries: int = 1,
) -> CommitteeReport:
    """Run the committee: call provider, validate output, persist report.

    Raises ValueError for budget/validation failures (non-retryable).
    Raises RuntimeError after exhausting retries on transient errors.

    The caller must have already called build_privacy_preview and obtained
    explicit Owner confirmation before calling this function.
    """
    from sqlalchemy import text

    if committee_session.status != "queued":
        raise ValueError("Session must be in 'queued' status to run")

    claimed = session.execute(
        text(
            "UPDATE committee_sessions SET status='running' "
            "WHERE id=:i AND status='queued' RETURNING id"
        ),
        {"i": committee_session.id},
    ).scalar()
    if not claimed:
        raise ValueError("Committee already claimed; no duplicate provider call")
    committee_session.status = "running"
    session.commit()

    try:
        candidate_id = session.execute(
            text("SELECT candidate_id FROM contribution_decisions WHERE committee_session_id=:s"),
            {"s": committee_session.id},
        ).scalar()
        if candidate_id:
            from apps.api.services.launch_investment import digest, validate_candidate

            candidate = validate_candidate(session, committee_session.household_id, candidate_id)
            evidence = committee_session.evidence_items
            if (
                prompt_version != "contribution-v1.1"
                or len(evidence) != 1
                or digest(evidence[0].structured_facts) != candidate["content_hash"]
                or evidence[0].content_hash != candidate["content_hash"]
            ):
                raise ValueError(
                    "Linked contribution requires exact deterministic evidence "
                    "and contribution prompt"
                )
        from apps.api.services.committee_evidence_registry import evidence_registry

        registry = evidence_registry(committee_session)
    except Exception:
        _fail_session(session, committee_session, "Invalid evidence/context")
        raise

    evidence_ids = {str(e.id) for e in committee_session.evidence_items}
    payload = _build_provider_payload(
        committee_session,
        committee_session.evidence_items,
    )
    token_estimate = len((json.dumps(payload) + prompt_for(prompt_version)).encode())

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

    # Budget covers all possible attempts before the first network call.
    try:
        rates = provider_rates(provider)
        budget = (token_estimate * rates[0] + MAX_OUTPUT_TOKENS * rates[1]) / 1_000_000
        if budget * (max_retries + 1) > MAX_COST_USD:
            raise ValueError("Provider cost budget exceeded")
        response = _call_with_retry(
            provider, payload, config, max_retries, system_prompt=prompt_for(prompt_version)
        )
    except Exception:
        _fail_session(session, committee_session, "Provider unavailable/budget rejected")
        raise
    if response.input_tokens < 0 or response.output_tokens < 0:
        _fail_session(session, committee_session, "Invalid usage")
        raise ValueError("Invalid provider token usage")
    if provider.provider_name == "deepseek" and (
        not response.input_tokens or not response.output_tokens
    ):
        _fail_session(session, committee_session, "Missing usage")
        raise ValueError("Provider usage required for cost evidence")
    actual_cost = (response.input_tokens * rates[0] + response.output_tokens * rates[1]) / 1_000_000
    if (
        actual_cost > MAX_COST_USD
        or response.output_tokens > MAX_OUTPUT_TOKENS
        or response.input_tokens > MAX_INPUT_TOKENS
    ):
        _fail_session(session, committee_session, "Usage exceeded budget")
        raise ValueError("Provider usage exceeded budget")

    # Parse JSON
    try:
        parsed = json.loads(response.raw_text)
    except json.JSONDecodeError as e:
        _fail_session(session, committee_session, f"Invalid JSON: {e}")
        raise ValueError(f"Provider returned invalid JSON: {e}")

    # Validate
    validation = validate_provider_output(parsed, evidence_ids, registry)
    if not validation.passed:
        error_detail = "; ".join(f"{e.field}: {e.message}" for e in validation.errors)
        _fail_session(session, committee_session, error_detail)
        raise ValueError(f"Output validation failed: {error_detail}")

    import re

    def inference_text(value):
        if isinstance(value, dict):
            return " ".join(
                inference_text(v)
                for k, v in value.items()
                if k not in {"evidence_id", "citation_ref"}
            )
        if isinstance(value, list):
            return " ".join(inference_text(v) for v in value)
        return str(value)

    numeric_pattern = (
        r"\d|[零〇一二三四五六七八九十百千万亿]|"
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
        r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
        r"trillion|half|quarter|percent|percentage)(?:fold)?\b"
    )
    if re.search(numeric_pattern, inference_text(parsed), re.I):
        _fail_session(session, committee_session, "Unsupported quantitative model assertion")
        raise ValueError("Numerical financial facts belong exclusively to deterministic evidence")

    if prompt_version == "contribution-v1.1":
        # Quantitative FACTs live exclusively in deterministic evidence. Model text is INFERENCE.
        def model_text(value):
            if isinstance(value, dict):
                return " ".join(
                    model_text(v)
                    for k, v in value.items()
                    if k not in {"evidence_id", "citation_ref"}
                )
            if isinstance(value, list):
                return " ".join(model_text(v) for v in value)
            return str(value)

        if re.search(
            numeric_pattern,
            model_text(parsed),
            re.I,
        ) or parsed.get("confidence") not in {
            "low",
            "medium",
            "high",
        }:
            _fail_session(
                session,
                committee_session,
                "Untrusted numerical assertion or missing qualitative confidence",
            )
            raise ValueError(
                "Contribution Committee must cite evidence without generating numerical facts"
            )
        parsed["classification"] = "INFERENCE"
        parsed["direction_classification"] = "RECOMMENDATION"

    parsed["classification"] = "INFERENCE"
    parsed["direction_classification"] = "RECOMMENDATION"

    # Persist immutable report
    report = _persist_report(
        session,
        committee_session,
        provider,
        parsed,
        response,
        prompt_version,
        schema_version,
        temperature,
        actual_cost,
    )
    committee_session.report = report
    committee_session.status = "completed"
    session.commit()

    # ── Sprint 008 Slice B: Committee notification dispatch ──
    _dispatch_committee_notification(committee_session)

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
    from apps.api.services.committee_evidence_registry import evidence_registry

    registry = evidence_registry(cs)
    return {
        "proposal": cs.proposal_text,
        "evidence": [
            {
                "evidence_id": str(e.id),
                "citation_claim": registry[str(e.id)]["claim"],
                "evidence_mode": registry[str(e.id)]["mode"],
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
    system_prompt: str = SYSTEM_PROMPT,
) -> ProviderResponse:
    user_prompt = json.dumps(payload)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return provider.call(system_prompt, user_prompt, config)
        except (ProviderTimeoutError, ProviderRateLimitError, ProviderServerError) as e:
            last_error = e
            if attempt < max_retries:
                continue
        except ProviderError:
            raise  # non-retryable — re-raise immediately

    raise RuntimeError(f"Provider call failed after {max_retries + 1} attempts: {last_error}")


def _persist_report(
    session: Session,
    cs: CommitteeSession,
    provider: AIModelProvider,
    parsed: dict,
    response: ProviderResponse,
    prompt_version: str,
    schema_version: str,
    temperature: Decimal,
    actual_cost: Decimal = Decimal(0),
) -> CommitteeReport:
    content_json = json.dumps(parsed, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()

    report = CommitteeReport(
        id=uuid4(),
        session_id=cs.id,
        provider=provider.provider_name,
        model_id=response.model or ProviderConfig().model,
        model_version=None,
        prompt_version=prompt_version,
        schema_version=schema_version,
        temperature=temperature,
        provider_params=None,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost=actual_cost,
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


def _dispatch_committee_notification(cs: CommitteeSession) -> None:
    """Dispatch committee session_complete notification after business commit.

    Sprint 008 Slice B — dedicated notification session, independent of
    the business transaction.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        from apps.api.database import SessionLocal
        from apps.api.services.notification_service import dispatch_notification

        ns = SessionLocal()
        try:
            dispatch_notification(
                ns,
                source="committee",
                event_type="session_complete",
                severity="info",
                household_id=cs.household_id,
                entity_id=str(cs.id),
                context={"session_id": str(cs.id)},
            )
        except Exception:
            ns.rollback()
            logger.warning(
                "Committee notification dispatch failed for session %s",
                cs.id,
            )
        finally:
            ns.close()
    except Exception:
        logger.warning(
            "Committee notification session unavailable",
        )
