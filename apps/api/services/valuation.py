"""Read-only valuation contract v1. Native ledger rows are never rewritten."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

MAX_AGE = timedelta(hours=24)


@dataclass
class Valuation:
    base_currency: str
    as_of: datetime
    entries: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    cost_estimate: bool = False
    trust_blockers: list[str] = field(default_factory=list)

    @property
    def status(self):
        return (
            "INCOMPLETE"
            if self.reasons
            else "COST_ESTIMATE"
            if self.cost_estimate
            else "DEGRADED"
            if self.trust_blockers
            else "COMPLETE"
        )

    @property
    def recommendation_ready(self):
        return self.status == "COMPLETE"

    @property
    def analysis_ready(self):
        """Descriptive risk analysis of reported amounts is not recommendation approval."""
        return not self.reasons and not self.cost_estimate

    def total(self, kind=None):
        if self.reasons:
            return None
        return sum(
            (e["base_value"] for e in self.entries if kind is None or e["kind"] == kind), Decimal(0)
        )

    def positions(self):
        if self.reasons:
            return []
        return [
            dict(e, market_value=e["base_value"]) for e in self.entries if e["kind"] == "position"
        ]

    def contract(self):
        return {
            "version": "valuation-v1",
            "base_currency": self.base_currency,
            "as_of": self.as_of.isoformat(),
            "status": self.status,
            "recommendation_ready": self.recommendation_ready,
            "reasons": self.reasons,
            "trust_blockers": self.trust_blockers,
            "readiness_status": "READY"
            if self.recommendation_ready
            else "BLOCKED"
            if self.reasons
            else "DEGRADED",
            "weight_scope": "positions_only",
            "freshness_hours": 24,
            "total_value": str(self.total()) if self.total() is not None else None,
            "inputs": [
                {
                    k: str(e[k]) if e.get(k) is not None else None
                    for k in (
                        "id",
                        "asset_id",
                        "kind",
                        "amount_currency",
                        "quantity",
                        "market_price",
                        "market_price_currency",
                        "price_unit_multiplier",
                        "native_value",
                        "base_value",
                        "price_source",
                        "price_as_of",
                        "unit_multiplier",
                        "quality_status",
                        "quote_quality",
                        "fx_source",
                        "fx_as_of",
                        "fx_rate",
                        "fx_observed_rate",
                        "fx_inverse",
                    )
                }
                for e in self.entries
            ],
        }


def _currency(currency):
    return ("GBP", Decimal("0.01")) if currency == "GBp" else (currency, Decimal(1))


def trusted_source(source):
    from apps.api.services.launch_providers import configured_data_sources

    try:
        return source in configured_data_sources()
    except ValueError:
        return False


def value_rows(base_currency, positions, cash, rates, as_of=None):
    """Pure evaluator: direct/inverse FX only; no partial aggregate or guessed FX."""
    result = Valuation(base_currency, as_of or datetime.now(timezone.utc))
    if not base_currency:
        result.reasons.append("Missing household base currency")
    for kind, rows in (("position", positions), ("cash", cash)):
        for row in rows:
            e = dict(row, kind=kind)
            key = str(row.get("id", "unknown"))
            stamp = row.get("market_price_as_of") or row.get("observed_at")
            currency = (
                row.get("currency")
                if kind == "cash"
                else (
                    row.get("market_value_currency")
                    if row.get("market_value") is not None
                    else row.get("market_price_currency")
                )
            )
            amount = row.get("amount") if kind == "cash" else row.get("market_value")
            e["price_source"] = row.get("source", "unknown")
            if kind == "position" and row.get("source") == "manual":
                result.cost_estimate = True
                e["price_quality"] = "COST_ESTIMATE"
            else:
                e["price_quality"] = row.get("quote_quality") or (
                    "REPORTED_VALUE" if amount is not None else "REPORTED_PRICE"
                )
            ccy, multiplier = _currency(currency)
            if kind == "position" and amount is None and row.get("market_price") is not None:
                amount = Decimal(str(row["quantity"])) * Decimal(str(row["market_price"]))
                ccy, multiplier = _currency(row.get("market_price_currency"))
            e.update(
                amount_currency=currency,
                unit_multiplier=str(multiplier),
                price_as_of=stamp,
                currency=ccy,
                base_value=None,
                fx_source=None,
                fx_as_of=None,
            )
            e["price_unit_multiplier"] = str(_currency(row.get("market_price_currency"))[1])
            errors = []
            if kind == "position":
                if row.get("quote_quality") in {"OBSERVED", "DELAYED"} and (
                    not row.get("identity_verified")
                    or not row.get("quote_identity_verified")
                    or not trusted_source(row.get("source"))
                ):
                    errors.append("QUOTE_IDENTITY_UNRESOLVED_OR_UNTRUSTED")
                if not row.get("identity_verified") or not row.get("quote_identity_verified"):
                    result.trust_blockers.append(f"position {key}: INSTRUMENT_IDENTITY_UNRESOLVED")
                if row.get("quote_quality") not in {"OBSERVED", "DELAYED"} or not trusted_source(
                    row.get("source")
                ):
                    result.trust_blockers.append(f"position {key}: UNTRUSTED_QUOTE")
            elif row.get("source") in {
                "simulation",
                "simulated",
                "synthetic",
            } and not trusted_source(row.get("source")):
                result.trust_blockers.append(f"cash {key}: UNTRUSTED_BALANCE")
            if kind == "position":
                price = row.get("market_price")
                if price is not None:
                    price = Decimal(str(price))
                    if not price.is_finite() or price <= 0:
                        errors.append("invalid market price")
            if amount is None or not ccy:
                errors.append("missing amount/price or amount currency")
            if stamp is None or stamp > result.as_of or result.as_of - stamp > MAX_AGE:
                errors.append("missing, future or stale price/balance observation")
            rate = None
            if ccy == base_currency and ccy:
                rate = Decimal(1)
                e["fx_source"] = "same_currency_identity"
            elif ccy:
                candidates = [
                    r
                    for r in rates
                    if r["observed_at"] <= result.as_of
                    and (r["from_currency"], r["to_currency"])
                    in ((ccy, base_currency), (base_currency, ccy))
                ]
                if candidates:
                    r = max(candidates, key=lambda r: r["observed_at"])
                    raw = Decimal(str(r["rate"]))
                    if raw.is_finite() and raw > 0 and result.as_of - r["observed_at"] <= MAX_AGE:
                        expected = {
                            "from_currency": r["from_currency"],
                            "to_currency": r["to_currency"],
                        }
                        identity = r.get("identity") or {}
                        if (
                            not trusted_source(r["rate_source"])
                            or r.get("quality") not in {"OBSERVED", "DELAYED"}
                            or any(identity.get(k) != v for k, v in expected.items())
                        ):
                            result.trust_blockers.append(f"{kind} {key}: UNTRUSTED_FX")
                        rate = raw if r["from_currency"] == ccy else Decimal(1) / raw
                        e.update(
                            fx_observed_rate=str(raw),
                            fx_source=r["rate_source"],
                            fx_as_of=r["observed_at"],
                            fx_inverse=r["from_currency"] != ccy,
                        )
                if rate is None:
                    errors.append("missing, invalid or stale FX")
            if amount is not None:
                native = Decimal(str(amount)) * multiplier
                e["native_value"] = native
                if not native.is_finite() or native < 0:
                    errors.append(
                        "non-finite or negative amount; liabilities require explicit modeling"
                    )
                elif rate is not None and not errors:
                    # Divide by the observed inverse rate directly; avoid
                    # rounding a reciprocal before multiplying a large amount.
                    e["base_value"] = native / raw if e.get("fx_inverse") else native * rate
            e["fx_rate"] = str(rate) if rate is not None else None
            e["quality_status"] = "INCOMPLETE" if errors else e["price_quality"]
            result.reasons.extend(f"{kind} {key}: {err}" for err in errors)
            result.entries.append(e)
    return result


def load_valuation(session, household_id, as_of=None):
    params = {"hid": household_id}
    base = session.execute(
        text("SELECT base_currency FROM household_profiles WHERE id=:hid"), params
    ).scalar()
    positions = (
        session.execute(
            text("""SELECT p.*, a.capital_bucket, ast.sector, ast.asset_class,
        ast.asset_type, ast.name, ast.symbol FROM positions p
        JOIN accounts a ON a.id=p.account_id JOIN portfolios pf ON pf.id=a.portfolio_id
        JOIN assets ast ON ast.id=p.asset_id WHERE pf.household_id=:hid AND p.is_latest=TRUE"""),
            params,
        )
        .mappings()
        .all()
    )
    cash = (
        session.execute(
            text("""SELECT cb.*, a.capital_bucket, a.account_type FROM cash_balances cb
        JOIN accounts a ON a.id=cb.account_id JOIN portfolios pf ON pf.id=a.portfolio_id
        WHERE pf.household_id=:hid AND cb.is_latest=TRUE"""),
            params,
        )
        .mappings()
        .all()
    )
    rates = (
        session.execute(
            text(
                "SELECT from_currency,to_currency,rate,rate_source,observed_at,identity,quality "
                "FROM fx_rates"
            )
        )
        .mappings()
        .all()
    )
    # Append-only quote projection: cost/quantity ledger and historical foreign keys unchanged.
    observations = (
        session.execute(
            text("""SELECT DISTINCT ON (o.asset_id) o.*, m.metadata AS instrument_metadata
        FROM market_observations o LEFT JOIN instrument_provider_mappings m
        ON m.asset_id=o.asset_id AND m.provider=o.provider
        ORDER BY o.asset_id,o.as_of DESC,o.received_at DESC"""),
            {"t": as_of or datetime.now(timezone.utc)},
        )
        .mappings()
        .all()
    )
    quotes = {o["asset_id"]: o for o in observations}
    projected = []
    for original in positions:
        row = dict(original)
        q = quotes.get(row["asset_id"])
        if q:
            from apps.api.models import Asset
            from apps.api.services.instrument_resolver import (
                Instrument,
                identity_dimensions,
                validate_asset_identity,
            )

            verified = False
            try:
                instrument = Instrument(**(q.get("instrument_metadata") or {}))
                validate_asset_identity(session.get(Asset, row["asset_id"]), instrument)
                verified = q.get("identity") == identity_dimensions(instrument)
                quote_ccy = "GBP" if q["currency"] == "GBp" else q["currency"]
                verified = verified and quote_ccy == instrument.currency
            except (ValueError, TypeError, KeyError):
                pass
            row.update(
                identity_verified=verified,
                quote_identity_verified=verified,
                market_value=None,
                market_value_currency=None,
                market_price=q["price"],
                market_price_currency=q["currency"],
                market_price_as_of=q["as_of"],
                source=q["provider"],
                quote_quality=q["quality"],
                asset_type=(q.get("instrument_metadata") or {}).get("asset_type")
                or row["asset_type"],
            )
        projected.append(row)
    return value_rows(base, projected, cash, rates, as_of)


class RecommendationUnavailable(ValueError):
    pass


def require_recommendation_ready(session, household_id):
    snapshot = load_valuation(session, household_id)
    if not snapshot.recommendation_ready:
        raise RecommendationUnavailable(
            "Recommendation unavailable: " + snapshot.status + "; " + "; ".join(snapshot.reasons)
        )
    return snapshot
