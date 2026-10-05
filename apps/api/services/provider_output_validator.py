"""Sprint 006 Slice B — Provider Output Validator.

Validates LLM output against schema, citation, safety, and language rules.
Rejects invalid output — never silently accepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_SECTIONS = [
    "supporting_arguments",
    "opposing_arguments",
    "risks",
    "policy_alignment",
    "minority_opinions",
    "evidence_citations",
    "limitations",
    "recommended_direction",
    "sections",
]

ALLOWED_DIRECTIONS = {
    "aligned_with_policy",
    "not_aligned_with_policy",
    "conditionally_aligned",
    "insufficient_evidence",
}

REQUIRED_ROLE_SECTIONS = [
    "long_term_compounding",
    "index_passive_investing",
    "macroeconomic_context",
    "risk_capital_preservation",
    "devils_advocate",
    "policy_alignment_role",
    "synthesis_chair",
]

FORBIDDEN_WORDS = {
    "buy",
    "sell",
    "hold",
    "short",
    "long",
    "execute",
    "order",
    "trade",
    "position",
    "purchase",
    "liquidate",
    "allocate to",
}

FORBIDDEN_PHRASES = [
    "you should buy",
    "you should sell",
    "i recommend buying",
    "i recommend selling",
    "invest in",
    "exit your position",
    "take profits",
    "cut losses",
    "this is investment advice",
    "guaranteed return",
    "risk-free",
]


# ═══════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ValidationError:
    field: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    passed: bool
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def accepted(cls) -> "ValidationResult":
        return cls(passed=True)

    @classmethod
    def rejected(cls, errors: list[ValidationError]) -> "ValidationResult":
        return cls(passed=False, errors=errors)


# ═══════════════════════════════════════════════════════════════════════════
# Validator
# ═══════════════════════════════════════════════════════════════════════════


def validate_provider_output(
    parsed: dict[str, Any],
    evidence_ids: set[str],
    registry: dict | None = None,
) -> ValidationResult:
    """Validate LLM output against all rules.

    Args:
        parsed: Parsed JSON from LLM response
        evidence_ids: Set of valid evidence IDs for this session

    Returns:
        ValidationResult with pass/fail and error details
    """
    errors: list[ValidationError] = []

    # 1. JSON structure (must fail fast on non-dict)
    structure_errors = _validate_structure(parsed)
    if structure_errors:
        return ValidationResult.rejected(structure_errors)
    errors.extend(_validate_required_sections(parsed))
    for key in [
        "supporting_arguments",
        "opposing_arguments",
        "risks",
        "minority_opinions",
        "limitations",
    ]:
        value = parsed.get(key)
        if not isinstance(value, list) or any(
            not isinstance(x, str) or not x.strip() for x in value
        ):
            errors.append(ValidationError(key, "Must be an array of nonempty strings"))
    if not isinstance(parsed.get("policy_alignment"), str):
        errors.append(ValidationError("policy_alignment", "Must be text"))
    if errors:
        return ValidationResult.rejected(errors)

    # 3. Opposing arguments non-empty
    errors.extend(_validate_opposing_arguments(parsed))

    # 4. Role sections
    errors.extend(_validate_role_sections(parsed))

    # 5. recommended_direction
    errors.extend(_validate_direction(parsed))

    # 6. Citation validation
    errors.extend(_validate_citations(parsed, evidence_ids, registry))

    # 7. Forbidden language
    errors.extend(_validate_language(parsed))

    # 8. Neutral language check
    errors.extend(_validate_neutral(parsed))

    # 9. Macro evidence declaration
    errors.extend(_validate_macro_evidence(parsed))

    if errors:
        return ValidationResult.rejected(errors)
    return ValidationResult.accepted()


# ═══════════════════════════════════════════════════════════════════════════
# Individual checks
# ═══════════════════════════════════════════════════════════════════════════


def _validate_structure(parsed: dict[str, Any]) -> list[ValidationError]:
    if not isinstance(parsed, dict):
        return [ValidationError("root", "Output must be a JSON object")]
    return []


def _validate_required_sections(parsed: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for section in REQUIRED_SECTIONS:
        if section not in parsed or parsed[section] is None:
            errors.append(ValidationError(section, f"Missing required section: {section}"))
    return errors


def _validate_opposing_arguments(parsed: dict[str, Any]) -> list[ValidationError]:
    args = parsed.get("opposing_arguments")
    if isinstance(args, list) and len(args) == 0:
        return [
            ValidationError(
                "opposing_arguments",
                "opposing_arguments must be non-empty",
            )
        ]
    if isinstance(args, str) and not args.strip():
        return [
            ValidationError(
                "opposing_arguments",
                "opposing_arguments must be non-empty",
            )
        ]
    return []


def _validate_role_sections(parsed: dict[str, Any]) -> list[ValidationError]:
    sections = parsed.get("sections", {})
    if not isinstance(sections, dict):
        return [ValidationError("sections", "sections must be an object")]
    errors: list[ValidationError] = []
    for role in REQUIRED_ROLE_SECTIONS:
        if role not in sections or sections[role] is None:
            errors.append(ValidationError(f"sections.{role}", f"Missing role section: {role}"))
    return errors


def _validate_direction(parsed: dict[str, Any]) -> list[ValidationError]:
    direction = parsed.get("recommended_direction", "")
    if not isinstance(direction, str) or direction not in ALLOWED_DIRECTIONS:
        return [
            ValidationError(
                "recommended_direction",
                f"Invalid direction '{direction}'. Allowed: {sorted(ALLOWED_DIRECTIONS)}",
            )
        ]
    return []


def _validate_citations(parsed, evidence_ids, registry=None):
    citations = parsed.get("evidence_citations")
    if not isinstance(citations, list):
        return [ValidationError("evidence_citations", "Must be a list")]
    errors = []
    if not citations and parsed.get("recommended_direction") != "insufficient_evidence":
        errors.append(
            ValidationError("evidence_citations", "Evidence-backed direction requires citations")
        )
    for i, citation in enumerate(citations):
        field = f"evidence_citations[{i}]"
        if (
            not isinstance(citation, dict)
            or set(citation) != {"evidence_id", "citation_ref", "claim"}
            or any(
                not isinstance(citation.get(k), str) or not citation[k].strip()
                for k in ("evidence_id", "citation_ref", "claim")
            )
        ):
            errors.append(ValidationError(field, "Citation requires exact ID, ref and claim"))
            continue
        eid = citation["evidence_id"]
        if eid not in evidence_ids:
            errors.append(
                ValidationError(field, "Evidence does not belong to this decision context")
            )
        elif registry is not None:
            expected = registry[eid]
            if (
                citation["citation_ref"] != expected["citation_ref"]
                or citation["claim"] != expected["claim"]
            ):
                errors.append(ValidationError(field, "Citation/provenance/classification mismatch"))
    return errors


def _validate_language(parsed: dict[str, Any]) -> list[ValidationError]:
    """Check for forbidden trading/investment-advice language."""
    text = _flatten_text(parsed).lower()
    errors: list[ValidationError] = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text:
            errors.append(
                ValidationError(
                    "language",
                    f"Forbidden phrase: '{phrase}'",
                )
            )
    return errors


def _validate_neutral(parsed: dict[str, Any]) -> list[ValidationError]:
    """Check for neutral language — detailed analysis deferred to Slice C."""
    _ = _flatten_text(parsed)
    return []


def _validate_macro_evidence(parsed: dict[str, Any]) -> list[ValidationError]:
    """Ensure macro section declares insufficient evidence when needed."""
    sections = parsed.get("sections", {})
    macro = sections.get("macroeconomic_context", "")
    if isinstance(macro, dict):
        macro = str(macro)
    if isinstance(macro, str) and macro.strip():
        return []
    return [
        ValidationError(
            "sections.macroeconomic_context",
            "Macroeconomic context section must be present and may declare"
            " insufficient current macro evidence",
        )
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _flatten_text(data: Any, depth: int = 0) -> str:
    """Recursively flatten nested dicts/lists to text for language checks."""
    if depth > 10:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_flatten_text(v, depth + 1) for v in data.values())
    if isinstance(data, list):
        return " ".join(_flatten_text(v, depth + 1) for v in data)
    return str(data) if data is not None else ""
