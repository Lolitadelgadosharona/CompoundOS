"""Typed evidence boundary. Historical analytics implementation is deferred from V1."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class HistoricalObservation:
    asset_id: str
    as_of: date
    adjusted_price: Decimal
    currency: str
    provider: str
    quality: str


@dataclass(frozen=True)
class BacktestRequest:
    base_currency: str
    observations: tuple[HistoricalObservation, ...]
    contributions: tuple[tuple[date, Decimal], ...]
    target_weights: tuple[tuple[str, Decimal], ...]


class BacktestService(Protocol):
    def analyze(self, request: BacktestRequest) -> dict: ...


def availability():
    return {
        "status": "DEFERRED",
        "classification": "EVIDENCE_ONLY",
        "recommendation_ready": False,
        "metrics": None,
        "reason": "No audited historical data/FX/corporate-action pipeline is enabled",
        "required_disclosures": [
            "Historical evidence is not a prediction",
            "Survivorship, adjusted prices, FX coverage and contribution timing",
        ],
    }
