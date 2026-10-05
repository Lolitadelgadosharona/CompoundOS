"""Published Policy evidence. Bucket bounds retain the existing positions-only semantics."""

from decimal import Decimal

from sqlalchemy import text


def published_buckets(session, version_id):
    return [
        dict(r)
        for r in session.execute(
            text(
                "SELECT bucket_name,target_pct,min_pct,max_pct FROM policy_capital_buckets "
                "WHERE version_id=:v ORDER BY bucket_name"
            ),
            {"v": version_id},
        ).mappings()
    ]


def bucket_findings(entries, buckets):
    positions = [e for e in entries if e["kind"] == "position"]
    total = sum((e["base_value"] for e in positions), Decimal(0))
    if not total:
        return []
    if any(not e.get("capital_bucket") for e in positions):
        return ["Published capital buckets cannot be evaluated: missing account bucket"]
    values = {}
    for e in positions:
        values[e["capital_bucket"]] = values.get(e["capital_bucket"], Decimal(0)) + e["base_value"]
    findings = []
    for b in buckets:
        pct = (values.get(b["bucket_name"], Decimal(0)) / total * 100).quantize(Decimal(".01"))
        if b["max_pct"] is not None and pct > b["max_pct"]:
            findings.append(f"Bucket {b['bucket_name']}: {pct}% (max {b['max_pct']}%)")
        elif b["min_pct"] is not None and pct < b["min_pct"]:
            findings.append(f"Bucket {b['bucket_name']}: {pct}% (min {b['min_pct']}%)")
    return findings


def funding_account(session, hid, settings):
    rows = list(
        session.execute(
            text(
                "SELECT a.id,a.capital_bucket,a.currency FROM accounts a JOIN portfolios p "
                "ON p.id=a.portfolio_id WHERE p.household_id=:h"
            ),
            {"h": hid},
        ).mappings()
    )
    selected = settings.get("funding_account_id")
    matches = [r for r in rows if str(r["id"]) == str(selected)] if selected else rows
    if len(matches) != 1 or not matches[0]["capital_bucket"]:
        raise ValueError("POLICY_EVALUATION_INCOMPLETE: select one owned funding account")
    if matches[0]["currency"] != settings["base_currency"]:
        raise ValueError(
            "POLICY_EVALUATION_INCOMPLETE: funding account must use plan base currency"
        )
    return dict(matches[0])
