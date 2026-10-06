"""Owner review semantic regressions, no external providers or real ledger writes."""

import copy
from datetime import datetime, timezone
from decimal import Decimal as D
from uuid import uuid4

import pytest

from apps.api.services import guardian_intelligence as gi
from apps.api.services.contribution_engine import contribution_plan
from apps.api.services.preview_review import discussion, lifecycle, strategy_view
from apps.api.services.valuation import Valuation
from tests.test_owner_preview import preview


def analysis(ready=True):
    return {
        "recommendation_ready": ready,
        "policy": {"status": "PASS", "findings": []},
        "guardian": {"status": "PASS", "findings": []},
        "plan": {"rows": []},
    }


def test_strategy_not_derived_from_holdings_or_import(monkeypatch):
    preview(monkeypatch)
    snapshot = {
        "configuration": {
            "id": "version",
            "strategy": {"approval": "OWNER"},
            "targets": [{"asset_id": "vti", "symbol": "VTI", "weight": "100"}],
        },
        "positions": [
            {"asset_id": "apple", "symbol": "AAPL", "kind": "position"},
            {"asset_id": "imported", "symbol": "NEW", "kind": "position"},
        ],
    }
    original = copy.deepcopy(snapshot)
    view = strategy_view(snapshot)
    targets = {t["symbol"]: t for t in view["targets"]}
    assert (
        targets["AAPL"]["weight"] == targets["BRK.B"]["weight"] == targets["NEW"]["weight"] == "0"
    )
    assert targets["NEW"]["status"] == "NON-TARGET HOLDING"
    assert snapshot == original and not view["sales_authorized"]


def test_real_engine_positive_strategy_only_conserves_capital():
    current = {symbol: D(20000) for symbol in ["VTI", "QQQ", "VXUS", "SGOV", "AAPL"]}
    targets = {"VTI": 50, "QQQ": 30, "VXUS": 10, "SGOV": 10}
    result = contribution_plan(current, targets, D(10000) / 7, D(100000) + D(10000) / 7)
    buys = {r["asset_id"]: D(r["buy_amount"]) for r in result["rows"]}
    assert "AAPL" not in buys and "BRK.B" not in buys
    assert buys["VTI"] > buys["QQQ"] > 0 and buys["SGOV"] == buys["VXUS"] == 0
    assert sum(buys.values()) + D(result["retained_cash"]) == D(result["new_capital"])
    with pytest.raises(ValueError):
        contribution_plan(current, {"VTI": 50}, 100, 100000)


def valuation(sector, kind="STOCK", value=100):
    return Valuation(
        "USD",
        datetime.now(timezone.utc),
        [
            {
                "id": uuid4(),
                "account_id": uuid4(),
                "asset_id": uuid4(),
                "base_value": D(value),
                "quantity": D(1),
                "observed_at": datetime.now(timezone.utc),
                "capital_bucket": "CORE",
                "sector": sector,
                "asset_type": kind,
                "kind": "position",
            }
        ],
    )


@pytest.mark.parametrize(
    "sector,kind", [(None, "STOCK"), ("Unclassified", "STOCK"), ("Technology", "ETF")]
)
def test_missing_sector_or_etf_lookthrough_not_known_risk(monkeypatch, sector, kind):
    preview(monkeypatch)
    monkeypatch.setattr(gi, "_load_policy_rule_threshold", lambda *args: D(40))
    results = gi.evaluate_sector_concentration(None, uuid4(), str(uuid4()), valuation(sector, kind))
    assert not any(r.exceeded for r in results)
    assert results[0].context["evaluation_status"] == "NOT_EVALUATED"


def test_known_sector_violation_preserved_with_partial_data(monkeypatch):
    preview(monkeypatch)
    monkeypatch.setattr(gi, "_load_policy_rule_threshold", lambda *args: D(40))
    v = valuation("Technology", value=80)
    v.entries += valuation(None, value=20).entries
    results = gi.evaluate_sector_concentration(None, uuid4(), str(uuid4()), v)
    assert any(r.exceeded and r.actual_value == D(80) for r in results)
    assert any((r.context or {}).get("evaluation_status") == "NOT_EVALUATED" for r in results)


def test_live_sector_behavior_unchanged(monkeypatch):
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "false")
    monkeypatch.setattr(gi, "_load_policy_rule_threshold", lambda *args: D(40))
    results = gi.evaluate_sector_concentration(None, uuid4(), str(uuid4()), valuation(None))
    assert results[0].exceeded and "Unclassified" in results[0].detail


@pytest.mark.parametrize(
    "status,committee,direction,expected",
    [
        ("not_reviewed", "not_requested", None, "CANDIDATE"),
        ("draft", "running", None, "REVIEWING"),
        ("draft", "completed", "aligned_with_policy", "READY_FOR_DECISION"),
        ("draft", "completed", "insufficient_evidence", "HOLD"),
        ("confirmed", "completed", "aligned_with_policy", "APPROVED"),
        ("rejected", "not_requested", None, "REJECTED"),
    ],
)
def test_existing_lifecycle_gates(status, committee, direction, expected):
    candidate = {
        "decision_status": status,
        "committee_status": committee,
        "committee_report": {"recommended_direction": direction} if direction else None,
    }
    assert lifecycle(analysis(), candidate, True) == expected
    if expected == "READY_FOR_DECISION":
        assert lifecycle(analysis(), candidate, False) == "CANDIDATE"
        assert lifecycle(analysis(False), candidate, True) == "NOT EVALUATED"


def test_blocked_discussion_is_not_validated_review_and_never_changes_plan(monkeypatch):
    preview(monkeypatch)
    a = analysis(False)
    a["guardian"]["status"] = "BLOCKED"
    a["guardian"]["findings"] = [
        {"detail": "Known concentration limit exceeded", "severity": "critical"}
    ]
    original = copy.deepcopy(a)
    result = discussion(a)
    assert result["overall"] == result["state"] == "BLOCKED"
    assert result["review_kind"].startswith("DISCUSSION ONLY")
    assert len(result["perspectives"]) == 6 and result["confidence"] == "NOT AVAILABLE"
    macro = next(p for p in result["perspectives"] if p["name"] == "MACRO ANALYST")
    assert macro["view"] == "NOT EVALUATED" and macro["evidence_references"] == []
    assert all(p["evidence_references"] for p in result["perspectives"] if p != macro)
    assert len(result["questions"]) == 6 and "new" in result["modification"]
    assert a == original
