"""Deterministic contribution-first allocation, Decimal only, no sale or trade side effects."""

from decimal import ROUND_DOWN, Decimal, InvalidOperation

D = Decimal
CENT = D("0.01")


def decimal_amount(value, nonnegative=True):
    try:
        x = D(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not x.is_finite() or (nonnegative and x < 0):
        raise ValueError("Amounts must be finite and nonnegative")
    return x


def contribution_plan(
    current, targets, contribution, total_value, reserve_pct=0, existing_cash=False
):
    """Fill positive post-contribution deficits proportionally. Remainder retained as cash.

    Weights use total wealth including cash. Exact cent conservation; stable UUID tie break.
    Incoming funds are planning inputs, not deposits to the authoritative ledger.
    """
    contribution = decimal_amount(contribution)
    total = decimal_amount(total_value)
    weights = {str(k): decimal_amount(v) for k, v in targets.items()}
    if not weights or sum(weights.values()) != 100 or any(v <= 0 for v in weights.values()):
        raise ValueError("Unique target weights must be positive and sum to 100%")
    current = {str(k): decimal_amount(v) for k, v in current.items()}
    if sum(current.values()) > total:
        raise ValueError("Asset values cannot exceed common portfolio valuation")
    reserve = decimal_amount(reserve_pct)
    if reserve > 100:
        raise ValueError("Cash floor must be between 0 and 100")
    cash_before = total - sum(current.values())
    if existing_cash and contribution > cash_before:
        raise ValueError("Initial funding exceeds recorded cash")
    post_total = total if existing_cash else total + contribution
    gaps = {k: max(D(0), post_total * w / 100 - current.get(k, D(0))) for k, w in weights.items()}
    cash_before = total - sum(current.values())
    available = max(
        D(0),
        min(
            contribution,
            cash_before + (D(0) if existing_cash else contribution) - post_total * reserve / 100,
        ),
    ).quantize(CENT, rounding=ROUND_DOWN)
    deficit = sum(gaps.values())
    spend = min(available, deficit).quantize(CENT, rounding=ROUND_DOWN)
    buys = {k: D(0) for k in weights}
    if deficit and spend:
        for k, g in gaps.items():
            buys[k] = (spend * g / deficit).quantize(CENT, rounding=ROUND_DOWN)
        remainder = spend - sum(buys.values())
        # Largest fractional remainder first; never exceed a deficit.
        order = sorted(gaps, key=lambda k: (-(spend * gaps[k] / deficit - buys[k]), k))
        for k in order:
            if remainder >= CENT and buys[k] + CENT <= gaps[k]:
                buys[k] += CENT
                remainder -= CENT
    rows = []
    for k, w in weights.items():
        value = current.get(k, D(0))
        weight = value / total * 100 if total else D(0)
        drift = weight - w
        rows.append(
            {
                "asset_id": k,
                "target_weight": str(w),
                "current_weight": str(weight),
                "absolute_drift": str(drift),
                "relative_drift": str(drift / w),
                "underweight": str(max(D(0), -drift)),
                "overweight": str(max(D(0), drift)),
                "buy_amount": str(buys[k]),
                "post_weight": str((value + buys[k]) / post_total * 100 if post_total else 0),
            }
        )
    retained = contribution - sum(buys.values())
    return {
        "classification": "RECOMMENDATION",
        "algorithm": "contribution-first-v1",
        "new_capital": str(contribution),
        "funding_source": "RECORDED_CASH" if existing_cash else "PLANNED_NEW_CONTRIBUTION",
        "portfolio_value": str(total),
        "post_value": str(post_total),
        "retained_cash": str(retained),
        "rounding_remainder": str(contribution - contribution.quantize(CENT, rounding=ROUND_DOWN)),
        "rows": rows,
        "execution": "MANUAL",
        "reason": "Use new money to fill positive target deficits; no sales",
        "weight_scope": "total_wealth_including_cash",
    }
