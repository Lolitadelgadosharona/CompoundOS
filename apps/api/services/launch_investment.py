"""V1 orchestration over existing ledger, Policy, Guardian, Committee and Journal.

No execution adapter. Evidence/configuration append-only; decision status belongs to Journal.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from apps.api.models import (
    Asset,
    AuditEvent,
    CommitteeEvidenceItem,
    CommitteeSession,
)
from apps.api.repositories.decisions import (
    get_current_published_version,
    get_household_id,
    get_policy_for_household,
)
from apps.api.repositories.policy_enrichment import list_version_rules
from apps.api.services import guardian_intelligence as gi
from apps.api.services.contribution_engine import contribution_plan, decimal_amount
from apps.api.services.instrument_resolver import (
    Instrument,
    InstrumentUnavailable,
    canonical_asset,
    resolve_query,
)
from apps.api.services.launch_providers import (
    get_fx_provider,
    get_instrument_provider,
    get_market_provider,
)
from apps.api.services.valuation import (
    MAX_AGE,
    RecommendationUnavailable,
    Valuation,
    load_valuation,
    value_rows,
)

D = Decimal


def encoded(value):
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def lock_household(session, hid):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:h,0))"), {"h": str(hid)})


def audit(session, hid, action, eid, metadata):
    session.add(
        AuditEvent(
            household_id=hid,
            actor="local-owner",
            action=action,
            entity_type="Contribution",
            entity_id=eid,
            event_metadata=metadata,
        )
    )
    session.flush()


def policy(session, hid):
    p = get_policy_for_household(session, hid)
    version = get_current_published_version(session, p.id) if p else None
    if not version:
        raise RecommendationUnavailable("Publish an Investment Policy first")
    return version


def configuration(session, hid):
    row = (
        session.execute(
            text(
                (
                    "SELECT * FROM investment_configurations WHERE household_id=:h ORDER BY"
                    " created_at DESC,id DESC LIMIT 1"
                )
            ),
            {"h": hid},
        )
        .mappings()
        .first()
    )
    if not row:
        raise RecommendationUnavailable("Investment configuration required")
    return row


def configure(session, hid, settings):
    lock_household(session, hid)
    v = policy(session, hid)
    base = session.execute(
        text("SELECT base_currency FROM household_profiles WHERE id=:h"), {"h": hid}
    ).scalar()
    if settings["base_currency"] != base:
        raise ValueError("Configuration base currency must match household")
    from apps.api.services.effective_policy import funding_account

    settings = dict(settings)
    settings["funding_account_id"] = str(funding_account(session, hid, settings)["id"])
    targets = settings["targets"]
    if len({t["asset_id"] for t in targets}) != len(targets):
        raise ValueError("Duplicate canonical target")
    contribution_plan({}, {t["asset_id"]: t["weight"] for t in targets}, 0, 0)
    decimal_amount(settings["monthly_amount"])
    decimal_amount(settings["initial_capital"])
    for t in targets:
        a = session.get(Asset, UUID(t["asset_id"]))
        if not a:
            raise ValueError("Unknown canonical target")
        # Require verified dynamic provider mapping rather than accepting guessed imported types.
        mapping = session.execute(
            text("SELECT 1 FROM instrument_provider_mappings WHERE asset_id=:a"), {"a": a.id}
        ).scalar()
        if not mapping:
            raise ValueError("Resolve target instrument before configuring")
    cid = uuid4()
    session.execute(
        text(
            (
                "INSERT INTO "
                "investment_configurations(id,household_id,policy_version_id,settings) "
                "VALUES(:i,:h,:p,CAST(:s AS jsonb))"
            )
        ),
        {"i": cid, "h": hid, "p": v.id, "s": encoded(settings)},
    )
    audit(session, hid, "contribution.configuration.created", cid, {"policy_version_id": str(v.id)})
    session.commit()
    return {"id": str(cid), "policy_version_id": str(v.id), **settings}


def mapped_instrument(session, aid):
    row = session.execute(
        text(
            (
                "SELECT metadata FROM instrument_provider_mappings WHERE asset_id=:a "
                "ORDER BY verified_at DESC LIMIT 1"
            )
        ),
        {"a": aid},
    ).scalar()
    if not row:
        asset = session.get(Asset, aid)
        if not asset or not asset.symbol:
            raise InstrumentUnavailable("Canonical instrument lacks provider identity")
        instrument = resolve_query(asset.symbol, get_instrument_provider())
        if instrument.currency != asset.currency or (
            asset.exchange and asset.exchange != instrument.exchange
        ):
            raise InstrumentUnavailable(
                "Imported instrument identity needs explicit reconciliation"
            )
        canonical = canonical_asset(session, instrument)
        if canonical.id != aid:
            raise InstrumentUnavailable(
                "Imported instrument identity does not match; preserve UUID"
            )
        return instrument
    instrument = Instrument(**row)
    from apps.api.services.instrument_resolver import validate_asset_identity

    validate_asset_identity(session.get(Asset, aid), instrument)
    return instrument


def trusted_source(source):
    from apps.api.services.valuation import trusted_source as trusted

    return trusted(source)


def check_observation(obs, now):
    stamp = obs.as_of
    amount = obs.price if hasattr(obs, "price") else obs.rate
    if (
        not amount.is_finite()
        or amount <= 0
        or stamp.tzinfo is None
        or stamp > now
        or now - stamp > MAX_AGE
    ):
        raise RecommendationUnavailable("Missing, invalid, future or stale price/FX observation")
    if obs.quality not in {"OBSERVED", "DELAYED"} or not obs.provider:
        raise RecommendationUnavailable("Untrusted market/FX source quality")


def refresh_data(session, hid):
    """Explicit Owner request. Append observations; never rewrite quantity/cost/cash."""
    lock_household(session, hid)
    now = datetime.now(timezone.utc)
    assets = set(
        session.execute(
            text("""SELECT p.asset_id FROM positions p JOIN accounts a ON a.id=p.account_id
        JOIN portfolios pf ON pf.id=a.portfolio_id WHERE pf.household_id=:h AND p.is_latest"""),
            {"h": hid},
        ).scalars()
    )
    try:
        settings = configuration(session, hid)["settings"]
        assets.update(UUID(t["asset_id"]) for t in settings["targets"])
    except RecommendationUnavailable:
        settings = None
    failures = []
    for aid in sorted(assets, key=str):
        try:
            instrument = mapped_instrument(session, aid)
            if instrument.asset_type == "CASH":
                continue
            obs = get_market_provider().price(instrument)
            check_observation(obs, now)
            from apps.api.services.instrument_resolver import identity_dimensions

            if (
                obs.provider != instrument.provider
                or obs.provider_id != instrument.provider_id
                or obs.identity != identity_dimensions(instrument)
                or ("GBP" if obs.currency == "GBp" else obs.currency) != instrument.currency
            ):
                raise InstrumentUnavailable("Quote/provider identity mismatch")
            session.execute(
                text(
                    (
                        "INSERT INTO "
                        "market_observations(id,asset_id,price,currency,as_of,provider,quality,identity)"
                        "\n                VALUES(:i,:a,:p,:c,:t,:s,:q,CAST(:identity AS jsonb))"
                    )
                ),
                {
                    "i": uuid4(),
                    "a": aid,
                    "p": obs.price,
                    "c": obs.currency,
                    "t": obs.as_of,
                    "s": obs.provider,
                    "q": obs.quality,
                    "identity": encoded(obs.identity),
                },
            )
        except (ValueError, InstrumentUnavailable) as exc:
            failures.append({"asset_id": str(aid), "reason": str(exc)})
    base = session.execute(
        text("SELECT base_currency FROM household_profiles WHERE id=:h"), {"h": hid}
    ).scalar()
    valuation = load_valuation(session, hid, now)
    currencies = {e["currency"] for e in valuation.entries if e.get("currency")}
    if settings:
        currencies.add(settings["monthly_currency"])
        for aid in assets:
            asset = session.get(Asset, aid)
            if asset:
                currencies.add(asset.currency)
    for currency in sorted(currencies - {base}):
        try:
            obs = get_fx_provider().fx(currency, base)
            check_observation(obs, now)
            if (
                (obs.base_currency, obs.quote_currency) != (currency, base)
                or not obs.identity
                or obs.identity.get("from_currency") != currency
                or obs.identity.get("to_currency") != base
            ):
                raise InstrumentUnavailable("FX pair mismatch")
            session.execute(
                text(
                    (
                        "INSERT INTO "
                        "fx_rates(id,from_currency,to_currency,rate,rate_source,observed_at,identity,quality)"
                        "\n                VALUES(:i,:f,:t,:r,:s,:d,CAST(:identity AS jsonb),:q)"
                    )
                ),
                {
                    "i": uuid4(),
                    "f": currency,
                    "t": base,
                    "r": obs.rate,
                    "s": obs.provider,
                    "d": obs.as_of,
                    "identity": encoded(obs.identity),
                    "q": obs.quality,
                },
            )
        except ValueError as exc:
            failures.append({"currency": currency, "reason": str(exc)})
    audit(
        session, hid, "contribution.data.refreshed", hid, {"failures": failures, "as_of": str(now)}
    )
    session.commit()
    return {"failures": failures, "valuation": load_valuation(session, hid).contract()}


def contribution_fx(session, settings, now):
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
    converted = value_rows(
        settings["base_currency"],
        [],
        [
            {
                "id": "planned_contribution",
                "currency": settings["monthly_currency"],
                "amount": settings["monthly_amount"],
                "observed_at": now,
                "source": "owner_configuration",
            }
        ],
        rates,
        now,
    )
    if not converted.recommendation_ready:
        raise RecommendationUnavailable("; ".join(converted.reasons))
    return converted


def policy_inputs(session, version):
    """Read existing published Policy only. Unsupported rules do not silently pass."""
    thresholds = {"_severity": {}}
    blockers = []
    for rule in list_version_rules(session, version.id):
        if not rule.enabled:
            continue
        if rule.rule_type in {
            "max_single_position_pct",
            "max_sector_concentration_pct",
            "min_cash_reserve_pct",
            "exploration_capital_limit",
        }:
            try:
                value = decimal_amount(rule.rule_value)
                if value > 100:
                    raise ValueError("percentage >100")
                thresholds[rule.rule_type] = value
                thresholds["_severity"][rule.rule_type] = rule.severity
            except ValueError:
                blockers.append("Invalid published rule " + rule.rule_type)
        elif rule.rule_type == "custom":
            try:
                custom = json.loads(rule.rule_value)
                if custom.get("schema") != "contribution-v1" or set(custom) - {
                    "schema",
                    "max_equity_pct",
                }:
                    raise ValueError("Unknown custom rule")
                thresholds["max_equity_pct"] = decimal_amount(custom["max_equity_pct"])
                if thresholds["max_equity_pct"] > 100:
                    raise ValueError("Invalid equity limit")
                thresholds["_severity"]["max_equity_pct"] = rule.severity
            except (ValueError, KeyError, TypeError, AttributeError):
                blockers.append("Published custom rule cannot be deterministically evaluated")
        elif rule.rule_type == "approval_required_for":
            # Every V1 plan already requires Committee and explicit Owner approval.
            continue
        else:
            blockers.append("Published rule requires review: " + rule.rule_type)
    # Legacy setup serializes limits in notes. Never silently omit or reinterpret them.
    try:
        notes = json.loads(version.notes)
    except (ValueError, TypeError):
        notes = {}
    if isinstance(notes, dict):
        for key, rule_type in [
            ("max_single_position_pct", "max_single_position_pct"),
            ("min_cash_pct", "min_cash_reserve_pct"),
        ]:
            if key not in notes:
                continue
            try:
                amount = decimal_amount(notes[key])
                matches = thresholds.get(rule_type) == amount
            except (ValueError, TypeError):
                matches = False
            if not matches:
                blockers.append("LEGACY_POLICY_LIMIT_RECONCILIATION_REQUIRED: " + key)

    # Preserve Policy prose; deterministic code cannot interpret arbitrary text.
    prohibited = version.prohibited_assets.strip()
    if prohibited.lower() in {"none", "no prohibited assets", "[]"}:
        prohibited = []
    else:
        try:
            prohibited = json.loads(prohibited)
            if not isinstance(prohibited, list) or any(not isinstance(x, str) for x in prohibited):
                raise ValueError("Not a symbol list")
        except (ValueError, TypeError):
            prohibited = []
            blockers.append("Prohibited-assets prose needs an explicit published symbol list")
    if version.leverage_policy.strip().lower() not in {
        "none",
        "no leverage",
        "leverage prohibited",
        "no margin or leverage",
        "prohibited",
    }:
        blockers.append("Leverage policy needs explicit prohibition for V1")
    from apps.api.services.instrument_resolver import normalize_symbol

    try:
        prohibited = [normalize_symbol(symbol) for symbol in prohibited]
    except ValueError:
        blockers.append("Invalid prohibited symbol in published Policy")
    return thresholds, prohibited, blockers


def state_fingerprint(session, hid, config):
    # Observation identities/times belong to candidate evidence; don't include changing wall-clock.
    tables = [
        (
            "positions",
            "p",
            "JOIN accounts a ON a.id=p.account_id JOIN portfolios pf ON pf.id=a.portfolio_id",
            "pf.household_id=:h AND p.is_latest",
        ),
        (
            "cash_balances",
            "p",
            "JOIN accounts a ON a.id=p.account_id JOIN portfolios pf ON pf.id=a.portfolio_id",
            "pf.household_id=:h AND p.is_latest",
        ),
    ]
    ledger = []
    for table, alias, joins, where in tables:
        rows = (
            session.execute(
                text(f"SELECT p.* FROM {table} p {joins} WHERE {where} ORDER BY p.id"), {"h": hid}
            )
            .mappings()
            .all()
        )
        ledger.append([dict(r) for r in rows])
    return digest(
        {"ledger": ledger, "configuration_id": str(config["id"]), "settings": config["settings"]}
    )


def evaluate(session, hid, config, now=None, funding="monthly"):
    now = now or datetime.now(timezone.utc)
    settings = config["settings"]
    version = policy(session, hid)
    if version.id != config["policy_version_id"]:
        raise RecommendationUnavailable("Published Policy changed; revise configuration")
    v = load_valuation(session, hid, now)
    if not v.recommendation_ready:
        raise RecommendationUnavailable(v.status + "; " + "; ".join(v.reasons))
    # Every target needs a real observed quote, even if not yet held.
    quotes = []
    for t in settings["targets"]:
        aid = UUID(t["asset_id"])
        instrument = mapped_instrument(session, aid)
        if instrument.asset_type == "CASH":
            raise RecommendationUnavailable(
                "Cash is a retained balance; use min_cash_reserve_pct, not a BUY target"
            )
        quote = (
            session.execute(
                text(
                    (
                        "SELECT * FROM market_observations WHERE asset_id=:a "
                        "ORDER BY as_of DESC,received_at DESC LIMIT 1"
                    )
                ),
                {"a": aid, "t": now},
            )
            .mappings()
            .first()
        )
        if (
            not quote
            or quote["as_of"] > now
            or now - quote["as_of"] > MAX_AGE
            or quote["quality"] not in {"OBSERVED", "DELAYED"}
            or not trusted_source(quote["provider"])
        ):
            raise RecommendationUnavailable("Missing/stale target price: " + instrument.symbol)
        from apps.api.services.instrument_resolver import identity_dimensions

        if quote.get("identity") != identity_dimensions(instrument):
            raise RecommendationUnavailable("QUOTE_IDENTITY_MISMATCH: target observation")
        if ("GBP" if quote["currency"] == "GBp" else quote["currency"]) != instrument.currency:
            raise RecommendationUnavailable("QUOTE_IDENTITY_MISMATCH: target currency")
        quotes.append({**dict(quote), "symbol": instrument.symbol, "classification": "FACT"})
    fx = (
        contribution_fx(session, settings, now)
        if funding == "monthly"
        else value_rows(
            settings["base_currency"],
            [],
            [
                {
                    "id": "initial_cash_budget",
                    "currency": settings["base_currency"],
                    "amount": settings["initial_capital"],
                    "observed_at": now,
                    "source": "owner_configuration",
                }
            ],
            [],
            now,
        )
    )
    # A reported import value cannot stand in for required market observations.
    for entry in v.positions():
        if entry.get("quote_quality") not in {"OBSERVED", "DELAYED"}:
            raise RecommendationUnavailable(
                "Observed price required for every held canonical asset"
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
    target_prices = value_rows(
        settings["base_currency"],
        [
            {
                "id": q["asset_id"],
                "quantity": D(1),
                "market_price": q["price"],
                "market_price_currency": q["currency"],
                "market_price_as_of": q["as_of"],
                "source": q["provider"],
                "quote_quality": q["quality"],
                "identity_verified": True,
                "quote_identity_verified": True,
            }
            for q in quotes
        ],
        [],
        rates,
        now,
    )
    for entry in v.entries + fx.entries + target_prices.entries:
        source = entry.get("fx_source")
        if source and source != "same_currency_identity" and not trusted_source(source):
            raise RecommendationUnavailable("Untrusted or simulated FX source")
        if entry["kind"] == "position" and not trusted_source(entry.get("price_source")):
            raise RecommendationUnavailable("Untrusted or simulated price source")
    if not target_prices.recommendation_ready:
        raise RecommendationUnavailable(
            "Target price/FX unavailable: " + "; ".join(target_prices.reasons)
        )
    thresholds, prohibited, policy_blocks = policy_inputs(session, version)
    policy_warnings = []
    from apps.api.services.effective_policy import (
        bucket_findings,
        funding_account,
        published_buckets,
    )

    try:
        destination = funding_account(session, hid, settings)
    except ValueError as exc:
        raise RecommendationUnavailable(str(exc)) from exc
    if funding == "initial":
        available = sum(
            (
                e["base_value"]
                for e in v.entries
                if e["kind"] == "cash" and str(e.get("account_id")) == str(destination["id"])
            ),
            D(0),
        )
        if fx.total() > available:
            raise RecommendationUnavailable("Initial capital exceeds selected funding account cash")
    buckets = published_buckets(session, version.id)
    current = {}
    for e in v.positions():
        key = str(e["asset_id"])
        current[key] = current.get(key, D(0)) + e["base_value"]
    plan = contribution_plan(
        current,
        {t["asset_id"]: t["weight"] for t in settings["targets"]},
        fx.total(),
        v.total(),
        thresholds.get("min_cash_reserve_pct", 0),
        existing_cash=funding == "initial",
    )
    post_cash = (
        D(plan["post_value"])
        - sum(current.values())
        - sum(D(r["buy_amount"]) for r in plan["rows"])
    )
    if D(plan["post_value"]) and post_cash / D(plan["post_value"]) * 100 < thresholds.get(
        "min_cash_reserve_pct", 0
    ):
        if thresholds["_severity"].get("min_cash_reserve_pct") == "warning":
            policy_warnings.append("Published cash floor remains unmet; purchases retained as cash")
        else:
            policy_blocks.append("Published minimum cash reserve remains unmet")
    positions = [dict(e) for e in v.positions()]
    reviews = {t["asset_id"]: t for t in settings["targets"]}
    # Product leverage is not inferred from a ticker or name. Owner attestation is labeled evidence.
    for aid in set(current) | {r["asset_id"] for r in plan["rows"] if D(r["buy_amount"]) > 0}:
        asset = session.get(Asset, UUID(aid))
        if mapped_instrument(session, UUID(aid)).asset_type in {"ETF", "FUND"}:
            status = reviews.get(aid, {}).get("leverage_status", "unknown")
            if status != "unleveraged":
                policy_blocks.append(
                    "Product leverage unverified or prohibited: " + str(asset.symbol)
                )
    equity_limit = thresholds.get("max_equity_pct")
    if equity_limit is not None:
        projected_values = dict(current)
        for r in plan["rows"]:
            projected_values[r["asset_id"]] = projected_values.get(r["asset_id"], D(0)) + D(
                r["buy_amount"]
            )
        equity_value = D(0)
        for aid, value in projected_values.items():
            asset = session.get(Asset, UUID(aid))
            exposure = (
                100
                if mapped_instrument(session, UUID(aid)).asset_type == "STOCK"
                else reviews.get(aid, {}).get("equity_exposure_pct")
            )
            if exposure is None:
                policy_blocks.append("Equity look-through exposure unknown: " + str(asset.symbol))
            else:
                equity_value += value * decimal_amount(exposure) / 100
        if D(plan["post_value"]) and equity_value / D(plan["post_value"]) * 100 > equity_limit:
            if thresholds["_severity"].get("max_equity_pct") == "warning":
                policy_warnings.append("Published equity allocation limit exceeded")
            else:
                policy_blocks.append("Published equity allocation limit exceeded")
    for row in plan["rows"]:
        asset = session.get(Asset, UUID(row["asset_id"]))
        row["symbol"] = asset.symbol
        if asset.symbol in prohibited and D(row["buy_amount"]) > 0:
            policy_blocks.append("Prohibited asset " + asset.symbol)
        amount = D(row["buy_amount"])
        if amount:
            # Projected position is evidence only, never written as an actual holding.
            positions.append(
                {
                    "id": uuid4(),
                    "asset_id": asset.id,
                    "account_id": destination["id"],
                    "base_value": amount,
                    "quantity": D(0),
                    "observed_at": now,
                    "capital_bucket": destination["capital_bucket"],
                    "sector": asset.sector,
                    "asset_type": asset.asset_type,
                    "kind": "position",
                }
            )
    policy_blocks.extend(bucket_findings(positions, buckets))
    projected = Valuation(v.base_currency, now, positions)
    guardian_findings = policy_guardian_findings(session, hid, version, projected, thresholds)
    if gi.has_active_critical_event(session, hid):
        guardian_findings.append(
            {
                "check": "active_critical_event",
                "severity": "critical",
                "detail": "Existing critical Guardian event blocks approval",
            }
        )
    legacy = confirmed_guardian_analysis(session, hid, version, v)
    projected_legacy = confirmed_guardian_analysis(session, hid, version, projected)
    guardian_findings += _confirmed_findings(legacy)
    guardian_findings += _confirmed_findings(projected_legacy)
    guardian_blocked = any(f.get("severity") == "critical" for f in guardian_findings)
    return {
        "classification": "FACT",
        "effective_policy": {
            "version_id": str(version.id),
            "bucket_weight_scope": "positions_only",
            "capital_buckets": buckets,
            "funding_account": destination,
            "blockers": policy_blocks,
            "warnings": policy_warnings,
        },
        "instrument_reviews_classification": "OWNER_ATTESTATION",
        "as_of": str(now),
        "configuration_id": str(config["id"]),
        "policy_version_id": str(version.id),
        "fingerprint": state_fingerprint(session, hid, config),
        "valuation": v.contract(),
        "market_data": quotes,
        "fx": fx.contract(),
        "target_price_valuation": target_prices.contract(),
        "funding": funding,
        "targets": settings["targets"],
        "monthly_contribution": {
            "amount": settings["monthly_amount"],
            "currency": settings["monthly_currency"],
        },
        "plan": plan,
        "policy": {
            "status": "BLOCKED" if policy_blocks else "WARNING" if policy_warnings else "PASS",
            "findings": policy_blocks + policy_warnings,
            "published_text": {
                k: getattr(version, k)
                for k in [
                    "prohibited_assets",
                    "leverage_policy",
                    "liquidity",
                    "diversification",
                    "decision_process",
                ]
            },
        },
        "guardian": {
            "status": "BLOCKED" if guardian_blocked else "WARNING" if guardian_findings else "PASS",
            "findings": guardian_findings,
            "current_analysis": legacy,
        },
        "recommendation_ready": not policy_blocks and not guardian_blocked,
    }


def make_candidate(session, hid, funding="monthly"):
    lock_household(session, hid)
    config = configuration(session, hid)
    evidence = evaluate(session, hid, config, funding=funding)
    cid = uuid4()
    now = datetime.now(timezone.utc)
    stamps = [datetime.fromisoformat(str(q["as_of"])) for q in evidence["market_data"]]
    for entry in evidence["valuation"]["inputs"] + evidence["fx"]["inputs"]:
        for key in ["price_as_of", "fx_as_of"]:
            if entry.get(key):
                stamps.append(datetime.fromisoformat(entry[key]))
    expiry = min([now + timedelta(hours=1)] + [s + MAX_AGE for s in stamps])
    session.execute(
        text(
            (
                "INSERT INTO "
                "contribution_candidates(id,household_id,configuration_id,evidence,content_hash,expires_at)"
                " VALUES(:i,:h,:c,CAST(:e AS jsonb),:s,:t)"
            )
        ),
        {
            "i": cid,
            "h": hid,
            "c": config["id"],
            "e": encoded(evidence),
            "s": digest(evidence),
            "t": expiry,
        },
    )
    audit(
        session,
        hid,
        "contribution.candidate.created",
        cid,
        {
            "content_hash": digest(evidence),
            "recommendation_ready": evidence["recommendation_ready"],
        },
    )
    session.commit()
    return candidate_detail(session, hid, cid)


def candidate_detail(session, hid, cid):
    row = (
        session.execute(
            text("SELECT * FROM contribution_candidates WHERE id=:i AND household_id=:h"),
            {"i": cid, "h": hid},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Candidate not found for household")
    result = {**dict(row), "id": str(row["id"])}
    link = (
        session.execute(
            text("SELECT * FROM contribution_decisions WHERE candidate_id=:i"), {"i": cid}
        )
        .mappings()
        .first()
    )
    if link:
        decision_status = session.execute(
            text("SELECT status FROM decisions WHERE id=:i"), {"i": link["decision_id"]}
        ).scalar()
        cs = session.get(CommitteeSession, link["committee_session_id"])
        result.update(
            decision_id=str(link["decision_id"]),
            decision_status=decision_status,
            committee_session_id=str(cs.id),
            committee_status=cs.status,
            committee_report=cs.report.report_content if cs.report else None,
        )
    else:
        result.update(decision_status="not_reviewed", committee_status="not_requested")
    if session.execute(
        text("SELECT 1 FROM audit_events WHERE entity_id=:i AND action='contribution.rejected'"),
        {"i": cid},
    ).scalar():
        result["decision_status"] = "rejected"
    return result


def validate_candidate(session, hid, cid):
    lock_household(session, hid)
    row = candidate_detail(session, hid, cid)
    if (
        row["expires_at"] <= datetime.now(timezone.utc)
        or digest(row["evidence"]) != row["content_hash"]
    ):
        raise RecommendationUnavailable("Candidate expired or evidence integrity failed")
    rejected = session.execute(
        text("SELECT 1 FROM audit_events WHERE entity_id=:i AND action='contribution.rejected'"),
        {"i": cid},
    ).scalar()
    if rejected:
        raise RecommendationUnavailable("Candidate rejected")
    config = configuration(session, hid)
    fresh = evaluate(session, hid, config, funding=row["evidence"].get("funding", "monthly"))
    if (
        fresh["fingerprint"] != row["evidence"]["fingerprint"]
        or fresh["policy_version_id"] != row["evidence"]["policy_version_id"]
    ):
        raise RecommendationUnavailable(
            "Ledger/configuration/Policy changed; generate a new candidate"
        )

    # Existing quote changes require a new committee review, not approval of a different plan.
    def stable(x):
        return [{k: str(v) for k, v in q.items() if k not in {"classification"}} for q in x]

    if stable(fresh["market_data"]) != stable(row["evidence"]["market_data"]):
        raise RecommendationUnavailable("Market observations changed; regenerate candidate")
    if (
        fresh["plan"] != row["evidence"]["plan"]
        or digest(fresh["effective_policy"]) != digest(row["evidence"].get("effective_policy"))
        or not fresh["recommendation_ready"]
        or fresh["valuation"]["inputs"] != row["evidence"]["valuation"]["inputs"]
        or [{k: v for k, v in e.items() if k != "price_as_of"} for e in fresh["fx"]["inputs"]]
        != [
            {k: v for k, v in e.items() if k != "price_as_of"}
            for e in row["evidence"]["fx"]["inputs"]
        ]
    ):
        raise RecommendationUnavailable(
            "Policy/Guardian blocked or FX changed; regenerate candidate"
        )
    return row


def preview_committee(session, hid, cid):
    row = validate_candidate(session, hid, cid)
    if row.get("decision_id"):
        return row
    from apps.api.decision_schemas import CreateDecisionRequest, UpdateDecisionDraftRequest
    from apps.api.services.committee_orchestration import create_committee_session
    from apps.api.services.decisions import create_decision, update_draft

    cs = create_committee_session(
        session,
        hid,
        "Contribution review",
        (
            "Review deterministic evidence; all model statements are INFERENCE. Do "
            "not supply numeric facts; cite evidence IDs. Quantitative facts remain"
            " in the evidence panel. No action before Owner approval. Return "
            "confidence as low, medium or high. Do not use digits in narrative or "
            "repeat numerical facts; refer to evidence citations instead."
        ),
    )
    fact = row["evidence"]
    item = CommitteeEvidenceItem(
        id=uuid4(),
        session_id=cs.id,
        source_type="portfolio_snapshot",
        source_id=None,
        source_title="FACT: deterministic contribution evidence",
        as_of=row["created_at"],
        content_hash=row["content_hash"],
        structured_facts=fact,
        provenance="compoundos_internal",
        freshness="candidate expires " + str(row["expires_at"]),
        confidence="high",
        citation_ref="contribution:" + str(cid),
    )
    session.add(item)
    decision, draft = create_decision(
        session, CreateDecisionRequest(title="Manual contribution plan")
    )
    draft = update_draft(
        session,
        decision.id,
        UpdateDecisionDraftRequest(
            expected_revision=draft.revision,
            decision_summary="Manual contribution-first plan; no trade execution",
            rationale=encoded(fact["plan"]),
            risks_and_uncertainties=(
                "Delayed prices; FX and market movement; manual execution required"
            ),
            evidence_or_sources="contribution_candidate="
            + str(cid)
            + "; hash="
            + row["content_hash"],
            expected_outcome="Reduce allocation drift using new funds",
            review_trigger="After manual execution or before candidate expiry",
            decision_date=date.today(),
        ),
    )
    session.execute(
        text(
            (
                "INSERT INTO "
                "contribution_decisions(candidate_id,decision_id,committee_session_id) "
                "VALUES(:c,:d,:s)"
            )
        ),
        {"c": cid, "d": decision.id, "s": cs.id},
    )
    audit(
        session,
        hid,
        "contribution.committee.previewed",
        cid,
        {"evidence_hash": row["content_hash"], "decision_id": str(decision.id)},
    )
    session.commit()
    return candidate_detail(session, hid, cid)


def guard_candidate_confirmation(session, hid, did, pid, draft):
    cid = session.execute(
        text("SELECT candidate_id FROM contribution_decisions WHERE decision_id=:i"), {"i": did}
    ).scalar()
    if not cid:
        return
    row = validate_candidate(session, hid, cid)
    cs = session.get(CommitteeSession, UUID(row["committee_session_id"]))
    import os

    if (
        cs.report
        and os.getenv("ENVIRONMENT", "").lower() != "test"
        and cs.report.provider != "deepseek"
    ):
        raise RecommendationUnavailable(
            "Simulated or unconfigured Committee provider cannot authorize a plan"
        )
    if (
        not cs.report
        or cs.status != "completed"
        or cs.report.schema_version != "hardening-1"
        or cs.report.prompt_version != "contribution-v1.1"
        or cs.report.report_content.get("recommended_direction") != "aligned_with_policy"
    ):
        raise RecommendationUnavailable(
            "Validated aligned Committee report required before manual approval"
        )
    from apps.api.services.committee_evidence_registry import evidence_registry
    from apps.api.services.provider_output_validator import validate_provider_output

    registry = evidence_registry(cs)
    if not validate_provider_output(cs.report.report_content, set(registry), registry).passed:
        raise RecommendationUnavailable("Committee evidence no longer validates")
    if str(pid) != row["evidence"]["policy_version_id"] or draft.rationale != encoded(
        row["evidence"]["plan"]
    ):
        raise RecommendationUnavailable(
            "Published Policy or execution plan differs from reviewed evidence"
        )
    if row["decision_status"] != "draft":
        raise RecommendationUnavailable("Candidate already decided")


def approve(session, hid, cid):
    row = validate_candidate(session, hid, cid)
    if not row.get("decision_id"):
        raise RecommendationUnavailable("Ask Committee first")
    from apps.api.services.decision_lifecycle import OwnerDecisionService

    OwnerDecisionService.confirm_decision(session, UUID(row["decision_id"]))
    audit(
        session,
        hid,
        "contribution.manual.approved",
        cid,
        {"execution": "MANUAL", "evidence_hash": row["content_hash"]},
    )
    session.commit()
    return {
        "status": "approved",
        "execution": "MANUAL",
        "plan": row["evidence"]["plan"],
        "decision_id": row["decision_id"],
    }


def require_research_target(session, run_id):
    if not run_id:
        raise RecommendationUnavailable("Research provenance unverified; regenerate research")
    params = session.execute(
        text(
            "SELECT rq.parameters FROM research_runs r "
            "JOIN research_requests rq ON rq.id=r.request_id WHERE r.id=:r"
        ),
        {"r": run_id},
    ).scalar()
    if not params or not params.get("asset_id") or not params.get("instrument"):
        raise RecommendationUnavailable(
            "INSTRUMENT_IDENTITY_UNRESOLVED: regenerate legacy research"
        )
    aid = UUID(params["asset_id"])
    from apps.api.services.instrument_resolver import identity_dimensions

    instrument = mapped_instrument(session, aid)
    if identity_dimensions(instrument) != identity_dimensions(Instrument(**params["instrument"])):
        raise RecommendationUnavailable("INSTRUMENT_IDENTITY_MISMATCH: research provenance")
    q = (
        session.execute(
            text(
                "SELECT * FROM market_observations WHERE asset_id=:a "
                "ORDER BY as_of DESC,received_at DESC LIMIT 1"
            ),
            {"a": aid},
        )
        .mappings()
        .first()
    )
    if not q or q.get("identity") != identity_dimensions(instrument):
        raise RecommendationUnavailable("QUOTE_IDENTITY_MISMATCH: research observation")
    now = datetime.now(timezone.utc)
    rates = session.execute(text("SELECT * FROM fx_rates")).mappings().all()
    base = session.execute(
        text("SELECT base_currency FROM household_profiles WHERE id=:h"),
        {"h": get_household_id(session)},
    ).scalar()
    v = value_rows(
        base,
        [
            dict(
                id=str(aid),
                quantity=D(1),
                market_price=q["price"],
                market_price_currency=q["currency"],
                market_price_as_of=q["as_of"],
                source=q["provider"],
                quote_quality=q["quality"],
                identity_verified=True,
                quote_identity_verified=True,
            )
        ],
        [],
        rates,
        now,
    )
    if (
        not v.recommendation_ready
        or ("GBP" if q["currency"] == "GBp" else q["currency"]) != instrument.currency
    ):
        raise RecommendationUnavailable("Research target valuation is not READY")
    return {
        "asset_id": str(aid),
        "identity": q["identity"],
        "price": str(q["price"]),
        "currency": q["currency"],
        "as_of": q["as_of"].isoformat(),
    }


def research_review_context(session, run_id):
    from apps.api.services.effective_policy import bucket_findings, published_buckets

    target = require_research_target(session, run_id)
    hid = get_household_id(session)
    snapshot = load_valuation(session, hid)
    if not snapshot.recommendation_ready:
        raise RecommendationUnavailable("Research valuation not READY")
    version = policy(session, hid)
    thresholds, prohibited, blockers = policy_inputs(session, version)
    buckets = published_buckets(session, version.id)
    blockers += bucket_findings(snapshot.entries, buckets)
    findings = policy_guardian_findings(session, hid, version, snapshot, thresholds)
    findings += confirmed_guardian_findings(session, hid, version, snapshot)
    blockers += [str(f["detail"]) for f in findings if f["severity"] == "critical"]
    if "max_equity_pct" in thresholds:
        blockers.append("Equity look-through requires a deterministic allocation plan")
    if (
        thresholds.get("min_cash_reserve_pct") is not None
        and snapshot.total()
        and snapshot.total("cash") / snapshot.total() * 100 < thresholds["min_cash_reserve_pct"]
        and thresholds["_severity"].get("min_cash_reserve_pct") == "critical"
    ):
        blockers.append("Published cash floor blocks research approval")
    if target["identity"]["symbol"] in prohibited:
        blockers.append("Research target prohibited by published Policy")
    if gi.has_active_critical_event(session, hid):
        blockers.append("Critical Guardian event blocks research approval")
    if blockers:
        raise RecommendationUnavailable(
            "Policy/Guardian research review blocked: " + "; ".join(blockers)
        )
    return {
        "target": target,
        "valuation_inputs": snapshot.contract()["inputs"],
        "policy_version_id": str(version.id),
        "capital_buckets": json.loads(encoded(buckets)),
        "guardian_findings": json.loads(encoded(findings)),
    }


def require_research_committee(session, run_id):
    """A research wrapper/draft is not a completed evidence-validated Committee."""
    import os

    from apps.api.services.committee_evidence_registry import evidence_registry
    from apps.api.services.provider_output_validator import validate_provider_output

    current_context = research_review_context(session, run_id)
    ids = (
        session.execute(
            text(
                "SELECT DISTINCT c.id FROM committee_sessions c JOIN committee_evidence_items e "
                "ON e.session_id=c.id WHERE e.structured_facts->>'run_id'=:r "
                "AND c.household_id=:h AND c.status='completed'"
            ),
            {"r": str(run_id), "h": get_household_id(session)},
        )
        .scalars()
        .all()
    )
    for sid in ids:
        cs = session.get(CommitteeSession, sid)
        report = cs.report
        if (
            not report
            or report.schema_version != "hardening-1"
            or report.report_content.get("recommended_direction")
            not in {"aligned_with_policy", "conditionally_aligned"}
            or (os.getenv("ENVIRONMENT") != "test" and report.provider != "deepseek")
        ):
            continue
        try:
            registry = evidence_registry(cs)
        except ValueError:
            continue
        valid = validate_provider_output(report.report_content, set(registry), registry)
        linked = {
            str(e.id)
            for e in cs.evidence_items
            if e.structured_facts.get("run_id") == str(run_id)
            and digest(e.structured_facts.get("review_context")) == digest(current_context)
        }
        cited = {c.get("evidence_id") for c in report.report_content.get("evidence_citations", [])}
        if valid.passed and linked & cited:
            return
    raise RecommendationUnavailable(
        "Validated research Committee required; draft/memo is insufficient"
    )


def policy_guardian_findings(session, hid, version, valuation, thresholds):
    guardian_findings = []
    for label, fn in [
        ("concentration", gi.evaluate_single_position_concentration),
        ("sector", gi.evaluate_sector_concentration),
        ("exploration", gi.evaluate_exploration_capital_limit),
    ]:
        for result in fn(session, hid, str(version.id), valuation=valuation):
            if result.exceeded:
                rule_type = {
                    "concentration": "max_single_position_pct",
                    "sector": "max_sector_concentration_pct",
                    "exploration": "exploration_capital_limit",
                }[label]
                guardian_findings.append(
                    {
                        "check": label,
                        "detail": result.detail,
                        "severity": thresholds["_severity"].get(rule_type, "warning"),
                    }
                )
    return guardian_findings


def confirmed_guardian_analysis(session, hid, version, valuation):
    from apps.api.services.guardian import _evaluate_current_ledger
    from apps.api.services.guardian_evaluator import PolicyAllocation

    allocations = (
        session.execute(
            text("SELECT * FROM investment_policy_version_allocations WHERE version_id=:p"),
            {"p": version.id},
        )
        .mappings()
        .all()
    )
    alloc = [
        PolicyAllocation(
            asset_class_name=r["asset_class_name"],
            normalized_name=r["normalized_asset_class_name"],
            target_percentage=r["target_percentage"],
        )
        for r in allocations
    ]
    return _evaluate_current_ledger(session, hid, date.today(), None, alloc, valuation)


def confirmed_guardian_findings(session, hid, version, valuation):
    return _confirmed_findings(confirmed_guardian_analysis(session, hid, version, valuation))


def _confirmed_findings(result):
    return [
        {"check": "confirmed_guardian", "detail": finding, "severity": finding["severity"]}
        for finding in result.get("analysis_findings", [])
        if finding.get("exceeded")
    ]
