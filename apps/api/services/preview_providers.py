"""Deterministic external inputs, isolated from LIVE provider registry."""

import json
from datetime import datetime, timezone
from decimal import Decimal

from apps.api.services.ai_provider import AIModelProvider, ProviderResponse
from apps.api.services.instrument_resolver import (
    Instrument,
    InstrumentUnavailable,
    identity_dimensions,
)
from apps.api.services.launch_providers import FXObservation, PriceObservation
from apps.api.services.owner_preview import require_preview


class DemoProvider:
    name = "DEMO_PROVIDER"
    test_only = True
    catalog = {
        "VTI": ("Total US Market DEMO", "ETF", "100"),
        "QQQ": ("Nasdaq Fund DEMO", "ETF", "200"),
        "VXUS": ("International Fund DEMO", "ETF", "50"),
        "SGOV": ("Treasury Fund DEMO", "ETF", "100"),
        "BRK.B": ("Berkshire Class B DEMO", "STOCK", "300"),
        "AAPL": ("Apple DEMO", "STOCK", "125"),
    }

    def __init__(self):
        require_preview()

    def identify(self, pid):
        require_preview()
        symbol = pid.upper().replace("BRK-B", "BRK.B")
        if symbol not in self.catalog:
            raise InstrumentUnavailable("Unsupported DEMO instrument")
        name, kind, _ = self.catalog[symbol]
        return Instrument(symbol, name, "DEMO_EXCHANGE", kind, "USD", self.name, symbol)

    def search(self, query):
        require_preview()
        q = query.strip().lower().replace("brk-b", "brk.b")
        return [
            self.identify(s)
            for s, values in self.catalog.items()
            if q in s.lower() or q in values[0].lower()
        ]

    def price(self, instrument):
        require_preview()
        actual = self.identify(instrument.provider_id)
        if identity_dimensions(actual) != identity_dimensions(instrument):
            raise InstrumentUnavailable("DEMO identity mismatch")
        return PriceObservation(
            actual.provider_id,
            Decimal(self.catalog[actual.symbol][2]),
            "USD",
            datetime.now(timezone.utc).replace(microsecond=0),
            self.name,
            "DEMO",
            identity_dimensions(actual),
        )

    def fx(self, base, quote):
        require_preview()
        if (base, quote) not in {("USD", "CNY"), ("CNY", "USD")}:
            raise InstrumentUnavailable("Unsupported DEMO FX pair")
        rate = Decimal(7) if base == "USD" else Decimal(1) / Decimal(7)
        return FXObservation(
            base,
            quote,
            rate,
            datetime.now(timezone.utc).replace(microsecond=0),
            self.name,
            "DEMO",
            {
                "from_currency": base,
                "to_currency": quote,
                "provider_id": "DEMO:" + base + "/" + quote,
            },
        )


class PreviewCommittee(AIModelProvider):
    def __init__(self, registry):
        require_preview()
        self.registry = registry

    @property
    def provider_name(self):
        return "SIMULATED_COMMITTEE"

    def call(self, system_prompt, user_prompt, config=None):
        require_preview()
        narrative = "[model inference] SIMULATED COMMITTEE: assess supplied evidence only"
        report = {
            "supporting_arguments": [narrative],
            "opposing_arguments": [
                "[model inference] Demonstration cannot establish real suitability"
            ],
            "risks": ["[model inference] DEMO inputs are not real market evidence"],
            "policy_alignment": "[model inference] Policy checks remain authoritative",
            "minority_opinions": ["[model inference] Review limitations carefully"],
            "limitations": ["SIMULATED COMMITTEE — NOT REAL AI ANALYSIS"],
            "recommended_direction": "aligned_with_policy"
            if self.registry
            else "insufficient_evidence",
            "confidence": "low",
            "sections": {
                name: narrative
                for name in (
                    "long_term_compounding",
                    "index_passive_investing",
                    "macroeconomic_context",
                    "risk_capital_preservation",
                    "devils_advocate",
                    "policy_alignment_role",
                    "synthesis_chair",
                )
            },
            "evidence_citations": [
                {"evidence_id": key, "citation_ref": item["citation_ref"], "claim": item["claim"]}
                for key, item in self.registry.items()
            ],
        }
        return ProviderResponse(
            raw_text=json.dumps(report),
            model="SIMULATED-COMMITTEE",
            input_tokens=0,
            output_tokens=0,
            duration_ms=1,
        )


def committee_provider(cs):
    from apps.api.services.owner_preview import enabled

    if enabled():
        from apps.api.services.committee_evidence_registry import evidence_registry

        return PreviewCommittee(evidence_registry(cs))
    from apps.api.services.ai_provider import DeepSeekProvider

    return DeepSeekProvider()
