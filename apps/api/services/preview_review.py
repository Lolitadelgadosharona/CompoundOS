"""Preview-only Owner read model. Never grants approval or changes a candidate."""

from apps.api.services.owner_preview import require_preview

# Conceptual DEMO classifications, not live fund facts or sector weights.
DEMO_EXPOSURES = {
    "VTI": {"security_type": "ETF", "asset_class": "Equity", "geography": "US"},
    "QQQ": {
        "security_type": "ETF",
        "asset_class": "Equity",
        "geography": "US",
        "style": "Large Growth",
    },
    "VXUS": {"security_type": "ETF", "asset_class": "Equity", "geography": "International"},
    "SGOV": {
        "security_type": "ETF",
        "asset_class": "Fixed Income",
        "asset_subclass": "US Treasury",
    },
    "AAPL": {"security_type": "STOCK", "asset_class": "Equity"},
    "BRK.B": {"security_type": "STOCK", "asset_class": "Equity"},
}

PERSPECTIVES = [
    (
        "LONG-TERM INVESTOR",
        "long_term_compounding",
        "SUPPORTIVE",
        "Contribution-first maintains strategic discipline and avoids unnecessary turnover.",
        "No future returns or long-term suitability have been established.",
    ),
    (
        "INDEX INVESTOR",
        "index_passive_investing",
        "CAUTION",
        (
            "Broad-market and international categories serve different roles; "
            "overlapping funds need scrutiny."
        ),
        "Costs, holdings overlap and precise diversification evidence are unavailable.",
    ),
    (
        "RISK MANAGER",
        "risk_capital_preservation",
        "CAUTION",
        (
            "Published Policy and Guardian findings are authoritative; incomplete "
            "coverage cannot imply safety."
        ),
        "Sector look-through, drawdown and tail-risk evidence are unavailable.",
    ),
    (
        "MACRO ANALYST",
        "macroeconomic_context",
        "NOT EVALUATED",
        "No current rates, inflation or economic-regime evidence is supplied.",
        "Macro conditions cannot be inferred from DEMO quotes.",
    ),
    (
        "QUANT ANALYST",
        "policy_alignment_role",
        "SUPPORTIVE",
        (
            "The deterministic engine fills positive strategic deficits with new "
            "capital; it does not propose sales."
        ),
        "A drift calculation does not establish expected performance or optimality.",
    ),
    (
        "DEVIL'S ADVOCATE",
        "devils_advocate",
        "CAUTION",
        (
            "The strategy may be inconsistent with concentration constraints; "
            "missing exposure evidence could conceal overlap."
        ),
        "DEMO inputs cannot demonstrate suitability or market resilience.",
    ),
]


def lifecycle(analysis, candidate=None, current=False):
    """Presentation mapping of existing states; not a new persisted state machine."""
    if candidate and current and candidate.get("decision_status") == "rejected":
        return "REJECTED"
    if candidate and candidate.get("decision_status") in {"confirmed", "archived"} and current:
        return "APPROVED"
    if not analysis:
        return "NOT EVALUATED"
    if analysis["policy"]["status"] == "BLOCKED" or analysis["guardian"]["status"] == "BLOCKED":
        return "BLOCKED"
    if not analysis["recommendation_ready"]:
        return "NOT EVALUATED"
    if not candidate or not current:
        return "CANDIDATE"
    if candidate.get("committee_status") in {"queued", "running"}:
        return "REVIEWING"
    report = candidate.get("committee_report")
    if candidate.get("committee_status") == "completed" and report:
        if (
            report.get("recommended_direction") == "aligned_with_policy"
            and candidate.get("decision_status") == "draft"
        ):
            return "READY_FOR_DECISION"
        return "HOLD"
    return "CANDIDATE"


def discussion(analysis, candidate=None, current=False):
    require_preview()
    from apps.api.services.launch_investment import digest

    state = lifecycle(analysis, candidate, current)
    report = candidate.get("committee_report") if candidate and current else None
    validated = bool(report and candidate.get("committee_status") == "completed")
    refs = (report or {}).get("evidence_citations", [])
    if analysis and not refs:
        refs = [
            {
                "evidence_id": digest(analysis),
                "citation_ref": "preview-analysis:" + digest(analysis),
                "claim": "Deterministic DEMO calculation and recorded safeguards; discussion only",
            }
        ]
    overall = "BLOCKED" if state == "BLOCKED" else "HOLD"
    if validated and state == "READY_FOR_DECISION":
        overall = (
            "APPROVE_WITH_CAUTION"
            if "WARNING" in {analysis["guardian"]["status"], analysis["policy"]["status"]}
            else "APPROVE"
        )
    if validated and report.get("recommended_direction") == "not_aligned_with_policy":
        overall = "REJECT"
    missing = [
        "Sector classification / ETF look-through unavailable",
        "Current macro evidence unavailable",
        "Costs, overlap, drawdown and tail-risk evidence unavailable",
        "DEMO inputs are not production evidence",
    ]
    perspectives = [
        {
            "name": name,
            "view": "BLOCKED" if name == "RISK MANAGER" and state == "BLOCKED" else view,
            "key_reason": (report or {}).get("sections", {}).get(section, reason),
            "evidence_references": [] if view == "NOT EVALUATED" else refs,
            "data_limitations": limitation,
        }
        for name, section, view, reason, limitation in PERSPECTIVES
    ]
    rows = analysis["plan"]["rows"] if analysis else []
    quant = {r["symbol"]: r for r in rows}

    def explanation(symbol):
        row = quant.get(symbol)
        if not row:
            return "No evaluated candidate data for this asset is available."
        return (
            "The deterministic candidate assigns "
            + row["buy_amount"]
            + " in base currency against target "
            + row["target_weight"]
            + "%. Current weight is "
            + row["current_weight"]
            + (
                "%. Only positive post-contribution deficits receive capital; amounts "
                "are calculations, not forecasts."
            )
        )

    return {
        "data_mode": "SIMULATED",
        "state": state,
        "overall": overall,
        "review_kind": "VALIDATED SIMULATED REVIEW"
        if validated
        else "DISCUSSION ONLY — GOVERNANCE REVIEW INCOMPLETE",
        "confidence": "NOT AVAILABLE",
        "confidence_reason": "No calibrated confidence methodology is defined",
        "perspectives": perspectives,
        "supporting_case": ["New capital reduces positive strategic gaps without forced sales."],
        "opposing_case": [
            (
                "Strategic intent can conflict with published limits; missing "
                "look-through prevents full risk assessment."
            )
        ],
        "key_risks": [
            f["detail"]
            for f in (analysis or {}).get("guardian", {}).get("findings", [])
            if f["severity"] != "not_evaluated"
        ],
        "data_limitations": missing,
        "what_changes_mind": [
            (
                "Complete trusted exposure evidence and a candidate that satisfies "
                "unchanged published safeguards."
            )
        ],
        "alternatives": [
            "Retain this month's contribution as cash pending review.",
            (
                "Owner may reconsider strategic distribution; any change requires a "
                "new candidate and all reviews."
            ),
        ],
        "modification": (
            "DEFERRED — no contribution override. A changed strategy must be "
            "explicitly saved, followed by a new Quant / Policy / Guardian / "
            "Committee review. Existing candidate is never replaced."
        ),
        "questions": [
            {"question": "Why are we not buying more QQQ?", "answer": explanation("QQQ")},
            {"question": "Why is VTI receiving more capital?", "answer": explanation("VTI")},
            {
                "question": "What is the strongest argument against this plan?",
                "answer": (
                    "Concentration constraints and missing exposure evidence challenge "
                    "this strategy. A computed allocation is not permission to proceed."
                ),
            },
            {
                "question": "What happens if technology stocks fall sharply?",
                "answer": (
                    "Losses and correlated exposures are possible. No holdings overlap, "
                    "stress model or return evidence is supplied; a numerical loss "
                    "estimate is NOT EVALUATED."
                ),
            },
            {
                "question": "Why not keep this month's contribution in cash?",
                "answer": (
                    "Retaining cash is an alternative pending safeguards and Owner "
                    "review. No forecast supports a claim that investing now outperforms "
                    "cash. This discussion changes no allocation."
                ),
            },
            {"question": "What evidence is missing?", "answer": "; ".join(missing)},
        ],
        "evidence_references": refs,
    }


def strategy_view(snapshot):
    require_preview()
    configuration = snapshot.get("configuration")
    if not configuration:
        return None
    targets = {t["asset_id"]: t for t in configuration["targets"]}
    assets = {p["asset_id"]: p["symbol"] for p in snapshot["positions"] if p["kind"] == "position"}
    assets.update({key: t["symbol"] for key, t in targets.items()})
    # Include resolved unheld DEMO outside-target instruments without making them targets.
    from apps.api.services.preview_providers import DemoProvider

    result = [
        {
            "asset_id": aid,
            "symbol": symbol,
            "weight": targets.get(aid, {}).get("weight", "0"),
            "status": "TARGET" if aid in targets else "NON-TARGET HOLDING",
            "metadata": dict(
                DEMO_EXPOSURES.get(symbol, {}),
                classification="DEMO CONCEPTUAL",
                sector="NOT EVALUATED",
                look_through="UNAVAILABLE",
            ),
        }
        for aid, symbol in assets.items()
    ]
    known = {r["symbol"] for r in result}
    result.extend(
        {
            "asset_id": None,
            "symbol": symbol,
            "weight": "0",
            "status": "OUTSIDE STRATEGY",
            "metadata": dict(
                DEMO_EXPOSURES.get(symbol, {}),
                classification="DEMO CONCEPTUAL",
                sector="NOT EVALUATED",
                look_through="UNAVAILABLE",
            ),
        }
        for symbol in DemoProvider.catalog
        if symbol not in known
    )
    return {
        "version_id": configuration["id"],
        "approval": configuration.get("strategy", {}).get(
            "approval", "LEGACY CONFIGURATION — OWNER REVIEW REQUIRED"
        ),
        "targets": result,
        "sales_authorized": False,
        "data_mode": "DEMO",
    }
