# ruff: noqa: F811
"""Real orchestration regressions, exclusively in fresh isolated PostgreSQL test DB."""

from decimal import Decimal as D

import pytest

from apps.api.services import launch_investment as svc
from apps.api.services.valuation import RecommendationUnavailable
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup
from tests.test_owner_preview import preview


@pytest.mark.postgres
@pytest.mark.parametrize("setup", [{"max_position": "20"}], indirect=True)
def test_missing_sector_and_known_critical_block_both_preserved(db_session, setup, monkeypatch):
    hid, _, _, _ = setup
    preview(monkeypatch)
    candidate = svc.make_candidate(db_session, hid, funding="initial")
    result = candidate["evidence"]
    assert not result["recommendation_ready"]
    assert result["guardian"]["status"] == "BLOCKED"
    assert any(
        f["check"] == "sector" and f["severity"] == "not_evaluated"
        for f in result["guardian"]["findings"]
    )
    assert any(
        f["check"] == "concentration" and f["severity"] == "critical"
        for f in result["guardian"]["findings"]
    )
    assert not any("Sector Unclassified" in f["detail"] for f in result["guardian"]["findings"])
    with pytest.raises(RecommendationUnavailable):
        svc.preview_committee(db_session, hid, candidate["id"])
    with pytest.raises(RecommendationUnavailable):
        svc.approve(db_session, hid, candidate["id"])


@pytest.mark.postgres
def test_modified_strategy_invalidates_exact_old_candidate(db_session, setup, monkeypatch):
    hid, _, _, _ = setup
    old = svc.make_candidate(db_session, hid)
    settings = dict(svc.configuration(db_session, hid)["settings"])
    settings["targets"] = [dict(t, weight=w) for t, w in zip(settings["targets"], ["45", "55"])]
    preview(monkeypatch)
    saved = svc.configure(db_session, hid, settings)
    assert saved["strategy"]["approval"] == "EXPLICIT_OWNER_CONFIGURATION"
    with pytest.raises(RecommendationUnavailable):
        svc.approve(db_session, hid, old["id"])
    new = svc.make_candidate(db_session, hid)
    assert new["id"] != old["id"] and new["committee_status"] == "not_requested"
    assert sum(D(t["weight"]) for t in new["evidence"]["targets"]) == 100


@pytest.mark.postgres
def test_seed_upgrade_is_once_only_and_preserves_subsequent_owner_strategy(
    db_session, setup, monkeypatch
):
    from apps.api.services.preview_seed import restore_review_strategy

    hid, _, _, _ = setup
    preview(monkeypatch)
    settings = dict(svc.configuration(db_session, hid)["settings"])
    settings["owner_review_strategy"] = "review-2"
    svc.configure(db_session, hid, settings)
    settings.pop("owner_review_strategy")
    settings["targets"] = [dict(t, weight=w) for t, w in zip(settings["targets"], ["45", "55"])]
    latest = svc.configure(db_session, hid, settings)
    restore_review_strategy(db_session, hid)
    assert str(svc.configuration(db_session, hid)["id"]) == latest["id"]
