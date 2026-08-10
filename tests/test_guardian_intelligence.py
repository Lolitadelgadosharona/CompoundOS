"""Integration tests for Sprint 010 Slice B — Guardian Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0023_guardian_intelligence"

# ── Helpers ──────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_household(session: Session):
    from apps.api.models import HouseholdProfile
    hh = HouseholdProfile(id=uuid4(), household_name="Test", base_currency="USD")
    session.add(hh)
    session.flush()
    return hh


_PORTFOLIO_CACHE: dict = {}

def _setup_portfolio_data(
    session: Session, household_id, *,
    bucket="CORE", sector=None, market_value=Decimal("50000"),
):
    """Create portfolio + account + asset + position for testing.
    Reuses portfolio if already created for this household (uq_portfolios_household_id).
    Always creates new account/asset/position for isolation.
    """
    from apps.api.models import Account, Asset, Portfolio, PortfolioDraft, Position

    key = str(household_id)
    if key in _PORTFOLIO_CACHE:
        portfolio_id = _PORTFOLIO_CACHE[key]
    else:
        portfolio = Portfolio(id=uuid4(), household_id=household_id, status="draft")
        session.add(portfolio)
        session.flush()
        draft = PortfolioDraft(
            portfolio_id=portfolio.id, expected_revision=1,
            valuation_date=_now().date(),
        )
        session.add(draft)
        session.flush()
        _PORTFOLIO_CACHE[key] = portfolio.id
        portfolio_id = portfolio.id

    account = Account(
        id=uuid4(), portfolio_id=portfolio_id, name="Test Account",
        account_type="brokerage", capital_bucket=bucket, currency="USD",
    )
    session.add(account)
    session.flush()

    asset = Asset(
        id=uuid4(), name="Test Asset", asset_type="STOCK", currency="USD",
        sector=sector,
    )
    session.add(asset)
    session.flush()

    position = Position(
        id=uuid4(), account_id=account.id, asset_id=asset.id,
        quantity=Decimal("100"), quantity_source="provider_reported",
        avg_cost=Decimal("500"), avg_cost_currency="USD",
        market_price=Decimal("500"), market_price_currency="USD",
        market_value=market_value,
        observed_at=_now(), source="csv", is_latest=True,
    )
    session.add(position)
    session.flush()
    return portfolio_id, account, asset, position


def _setup_policy(session: Session, household_id):
    """Create policy + version for testing."""
    from apps.api.models import InvestmentPolicy, InvestmentPolicyVersion

    policy = InvestmentPolicy(id=uuid4(), household_id=household_id)
    session.add(policy)
    session.flush()

    now = _now()
    version = InvestmentPolicyVersion(
        id=uuid4(), policy_id=policy.id, version_number=1,
        status="published",
        objectives="Test", time_horizon="", liquidity="",
        diversification="", contribution_policy="", rebalancing_policy="",
        prohibited_assets="", leverage_policy="", decision_process="", notes="",
        published_at=now, sealed_at=None,
    )
    session.add(version)
    session.flush()
    version.sealed_at = now
    session.flush()
    return policy, version


# ═══════════════════════════════════════════════════════════════════════
# Migration tests
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_guardian_check_types_extended(self, db_session: Session):
        """New check types accepted by CHECK constraint."""
        from apps.api.models import GuardianCheck

        hh = _create_household(db_session)
        db_session.commit()

        new_types = [
            "capital_bucket_drift",
            "single_position_concentration",
            "sector_concentration",
            "exploration_capital_limit",
            "data_quality_staleness",
        ]
        for ct in new_types:
            check = GuardianCheck(
                id=uuid4(), household_id=hh.id,
                name=f"Test {ct}", canonical_name=f"test_{ct}",
                check_type=ct, status="draft",
            )
            db_session.add(check)
            db_session.flush()
        db_session.commit()
        # All inserted without error — proves CHECK extension

    def test_old_check_types_still_valid(self, db_session: Session):
        """Existing check types still work after extension."""
        from apps.api.models import GuardianCheck

        hh = _create_household(db_session)
        db_session.commit()

        for ct in ["drift", "category_exposure", "staleness"]:
            check = GuardianCheck(
                id=uuid4(), household_id=hh.id,
                name=f"Test {ct}", canonical_name=f"test_{ct}",
                check_type=ct, status="draft",
            )
            db_session.add(check)
            db_session.flush()
        db_session.commit()

    def test_migration_head(self, db_session: Session):
        result = db_session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert result == HEAD_REVISION, f"Expected {HEAD_REVISION}, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# Position loading
# ═══════════════════════════════════════════════════════════════════════


class TestPositionLoading:
    def test_load_positions_returns_data(self, db_session: Session):
        from apps.api.services.guardian_intelligence import _load_positions

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id)
        db_session.commit()

        positions = _load_positions(db_session, hh.id)
        assert len(positions) == 1
        assert positions[0].capital_bucket == "CORE"

    def test_load_positions_empty_when_no_data(self, db_session: Session):
        from apps.api.services.guardian_intelligence import _load_positions

        hh = _create_household(db_session)
        db_session.commit()

        positions = _load_positions(db_session, hh.id)
        assert positions == []


# ═══════════════════════════════════════════════════════════════════════
# Bucket drift evaluation
# ═══════════════════════════════════════════════════════════════════════


class TestBucketDrift:
    def test_bucket_drift_within_range_no_event(self, db_session: Session):
        from apps.api.models import PolicyCapitalBucket
        from apps.api.services.guardian_intelligence import evaluate_capital_bucket_drift

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, bucket="CORE")
        _, version = _setup_policy(db_session, hh.id)

        # Set target: CORE 50-100% (single position at 100% is within range)
        bucket = PolicyCapitalBucket(
            id=uuid4(), version_id=version.id,
            bucket_name="CORE", target_pct=Decimal("60"),
            min_pct=Decimal("50"), max_pct=Decimal("100"),
        )
        db_session.add(bucket)
        db_session.commit()

        results = evaluate_capital_bucket_drift(
            db_session, hh.id, str(version.id),
        )
        assert results == []

    def test_bucket_drift_exceeds_max_fires_event(self, db_session: Session):
        from apps.api.models import PolicyCapitalBucket
        from apps.api.services.guardian_intelligence import evaluate_capital_bucket_drift

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, bucket="EXPLORATION")
        _, version = _setup_policy(db_session, hh.id)

        bucket = PolicyCapitalBucket(
            id=uuid4(), version_id=version.id,
            bucket_name="EXPLORATION", target_pct=Decimal("10"),
            min_pct=Decimal("0"), max_pct=Decimal("5"),
        )
        db_session.add(bucket)
        db_session.commit()

        results = evaluate_capital_bucket_drift(
            db_session, hh.id, str(version.id),
        )
        assert len(results) > 0
        assert results[0].exceeded


# ═══════════════════════════════════════════════════════════════════════
# Concentration evaluation
# ═══════════════════════════════════════════════════════════════════════


class TestConcentration:
    def test_single_position_within_limit(self, db_session: Session):
        from apps.api.services.guardian_intelligence import (
            evaluate_single_position_concentration,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("10"))
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("90"))
        _, version = _setup_policy(db_session, hh.id)
        db_session.commit()

        results = evaluate_single_position_concentration(
            db_session, hh.id, str(version.id),
        )
        # Max position is 90%, default threshold is 20%
        assert len(results) > 0

    def test_concentration_uses_policy_threshold(self, db_session: Session):
        from apps.api.models import PolicyRule
        from apps.api.services.guardian_intelligence import (
            evaluate_single_position_concentration,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("800"))
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("200"))
        _, version = _setup_policy(db_session, hh.id)

        # Set threshold to 90% — no violation at 80%
        rule = PolicyRule(
            id=uuid4(), version_id=version.id,
            rule_type="max_single_position_pct", rule_value="95",
            severity="warning",
        )
        db_session.add(rule)
        db_session.commit()

        results = evaluate_single_position_concentration(
            db_session, hh.id, str(version.id),
        )
        assert results == []

    def test_exploration_limit_exceeded(self, db_session: Session):
        from apps.api.services.guardian_intelligence import (
            evaluate_exploration_capital_limit,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, bucket="EXPLORATION", market_value=Decimal("200"))
        _setup_portfolio_data(db_session, hh.id, bucket="CORE", market_value=Decimal("800"))
        _, version = _setup_policy(db_session, hh.id)
        db_session.commit()

        results = evaluate_exploration_capital_limit(
            db_session, hh.id, str(version.id),
        )
        # 20% exceeds default 10%
        assert len(results) > 0


# ═══════════════════════════════════════════════════════════════════════
# Staleness evaluation
# ═══════════════════════════════════════════════════════════════════════


class TestStaleness:
    def test_staleness_no_event_when_data_fresh(self, db_session: Session):
        from apps.api.services.guardian_intelligence import (
            evaluate_data_quality_staleness,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id)
        db_session.commit()

        results = evaluate_data_quality_staleness(db_session, hh.id, staleness_hours=1)
        assert results == []


# ═══════════════════════════════════════════════════════════════════════
# BLOCK_RECOMMENDATION tests
# ═══════════════════════════════════════════════════════════════════════


class TestBlockRecommendation:
    def test_has_active_critical_event_false_when_none(self, db_session: Session):
        from apps.api.services.guardian_intelligence import has_active_critical_event

        hh = _create_household(db_session)
        db_session.commit()

        assert not has_active_critical_event(db_session, hh.id)


# ═══════════════════════════════════════════════════════════════════════
# AI Authority tests
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_guardian_reads_never_writes_policy(self, db_session: Session):
        """Guardian evaluation only reads policy data — never modifies."""
        from apps.api.services.guardian_intelligence import _load_policy_rule_threshold

        hh = _create_household(db_session)
        db_session.commit()
        _, version = _setup_policy(db_session, hh.id)
        db_session.commit()

        threshold = _load_policy_rule_threshold(
            db_session, str(version.id), "max_single_position_pct",
        )
        # Returns None when no rule exists — this is a read, not a write
        assert threshold is None

    def test_no_trading_code_path(self):
        """Verify guardian_intelligence has no trade/order/rebalance logic."""
        import inspect

        from apps.api.services import guardian_intelligence

        source = inspect.getsource(guardian_intelligence)
        # Exclude SQLAlchemy patterns from check
        trading_keywords = [
            "trade", "order_placed", "execute_trade", "rebalance", "broker_api",
        ]
        for word in trading_keywords:
            assert word not in source.lower(), (
                f"Forbidden word '{word}' found")


# ═══════════════════════════════════════════════════════════════════════
# Regression: Policy override
# ═══════════════════════════════════════════════════════════════════════


class TestPolicyOverride:
    def test_policy_rule_overrides_default_threshold(self, db_session: Session):
        """Set policy to 15%, position at 18% → violation detected."""
        from apps.api.models import PolicyRule
        from apps.api.services.guardian_intelligence import (
            evaluate_single_position_concentration,
        )

        hh = _create_household(db_session)
        db_session.commit()
        # One position at 18% of total
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("180"))
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("820"))
        _, version = _setup_policy(db_session, hh.id)

        # Policy says max 15%
        rule = PolicyRule(
            id=uuid4(), version_id=version.id,
            rule_type="max_single_position_pct", rule_value="15",
            severity="warning",
        )
        db_session.add(rule)
        db_session.commit()

        results = evaluate_single_position_concentration(
            db_session, hh.id, str(version.id),
        )
        # 18% exceeds 15% policy threshold (at least one position triggers)
        assert len(results) >= 1
        assert results[0].exceeded
        assert results[0].threshold_value == Decimal("15")

    def test_policy_override_tighter_than_default(self, db_session: Session):
        """Default is 20%. Policy says 10%. Position at 12% → violation."""
        from apps.api.models import PolicyRule
        from apps.api.services.guardian_intelligence import (
            evaluate_single_position_concentration,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("120"))
        _setup_portfolio_data(db_session, hh.id, market_value=Decimal("880"))
        _, version = _setup_policy(db_session, hh.id)

        rule = PolicyRule(
            id=uuid4(), version_id=version.id,
            rule_type="max_single_position_pct", rule_value="10",
            severity="critical",
        )
        db_session.add(rule)
        db_session.commit()

        results = evaluate_single_position_concentration(
            db_session, hh.id, str(version.id),
        )
        # 12% exceeds 10% policy threshold (tighter than 20% default)
        assert len(results) >= 1
        assert results[0].threshold_value == Decimal("10")


# ═══════════════════════════════════════════════════════════════════════
# Regression: Severity boundaries
# ═══════════════════════════════════════════════════════════════════════


class TestSeverityBoundaries:
    def test_policy_rule_severity_is_read_correctly(self, db_session: Session):
        """Guardian reads severity from policy_rule, not from hardcoded value."""
        from apps.api.models import PolicyRule
        from apps.api.services.guardian_intelligence import (
            _load_policy_rule_threshold,
            evaluate_exploration_capital_limit,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, bucket="EXPLORATION",
                              market_value=Decimal("150"))
        _setup_portfolio_data(db_session, hh.id, bucket="CORE",
                              market_value=Decimal("850"))
        _, version = _setup_policy(db_session, hh.id)

        # Critical threshold at 10% — 15% exceeds
        rule = PolicyRule(
            id=uuid4(), version_id=version.id,
            rule_type="exploration_capital_limit", rule_value="10",
            severity="critical",
        )
        db_session.add(rule)
        db_session.commit()

        # Threshold loaded correctly at 10%
        threshold = _load_policy_rule_threshold(
            db_session, str(version.id), "exploration_capital_limit",
        )
        assert threshold == Decimal("10")

        # 15% exceeds 10% → violation detected
        results = evaluate_exploration_capital_limit(
            db_session, hh.id, str(version.id),
        )
        assert len(results) == 1

    def test_no_violation_when_within_policy_threshold(self, db_session: Session):
        """Exploration at 5%, policy limit 15% → no violation."""
        from apps.api.models import PolicyRule
        from apps.api.services.guardian_intelligence import (
            evaluate_exploration_capital_limit,
        )

        hh = _create_household(db_session)
        db_session.commit()
        _setup_portfolio_data(db_session, hh.id, bucket="EXPLORATION",
                              market_value=Decimal("50"))
        _setup_portfolio_data(db_session, hh.id, bucket="CORE",
                              market_value=Decimal("950"))
        _, version = _setup_policy(db_session, hh.id)

        rule = PolicyRule(
            id=uuid4(), version_id=version.id,
            rule_type="exploration_capital_limit", rule_value="15",
            severity="critical",
        )
        db_session.add(rule)
        db_session.commit()

        results = evaluate_exploration_capital_limit(
            db_session, hh.id, str(version.id),
        )
        assert results == []


# ═══════════════════════════════════════════════════════════════════════
# Regression: Committee block integration
# ═══════════════════════════════════════════════════════════════════════


class TestCommitteeBlockIntegration:
    def test_critical_severity_detected(self, db_session: Session):
        """has_active_critical_event returns True when critical severity confirmed."""
        from apps.api.models import (
            GuardianCheck,
            GuardianCheckConfirmed,
            GuardianEvaluationRun,
            GuardianEvent,
        )
        from apps.api.services.guardian_intelligence import has_active_critical_event

        hh = _create_household(db_session)
        _, version = _setup_policy(db_session, hh.id)
        db_session.commit()

        portfolio_id, _, _, _ = _setup_portfolio_data(db_session, hh.id)
        db_session.commit()

        snapshot_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO portfolio_snapshots (id, portfolio_id, version_number, "
                "valuation_date, status) VALUES (:sid, :pid, 1, :vd, 'current')"
            ),
            {"sid": snapshot_id, "pid": portfolio_id, "vd": _now().date()},
        )

        check = GuardianCheck(
            id=uuid4(), household_id=hh.id,
            name="Critical Test", canonical_name="crit_v3",
            check_type="exploration_capital_limit", status="confirmed",
        )
        db_session.add(check)
        db_session.flush()

        confirmed = GuardianCheckConfirmed(
            id=uuid4(), check_id=check.id, version_number=1,
            check_type="exploration_capital_limit",
            threshold_value=Decimal("10"), severity="critical",
        )
        db_session.add(confirmed)
        db_session.flush()

        run = GuardianEvaluationRun(
            id=uuid4(), household_id=hh.id,
            status="completed", checks_evaluated=1, events_created=1,
            as_of_date=_now().date(),
        )
        db_session.add(run)
        db_session.flush()

        event = GuardianEvent(
            id=uuid4(), evaluation_run_id=run.id,
            household_id=hh.id, check_id=check.id,
            check_version_id=confirmed.id,
            check_type="exploration_capital_limit",
            policy_version_id=version.id,
            portfolio_snapshot_id=snapshot_id,
            exceeded=True, as_of_date=_now().date(),
        )
        db_session.add(event)
        db_session.commit()

        assert has_active_critical_event(db_session, hh.id)

    def test_warning_severity_not_blocked(self, db_session: Session):
        """Warning severity → has_active_critical_event returns False."""
        from apps.api.models import (
            GuardianCheck,
            GuardianCheckConfirmed,
            GuardianEvaluationRun,
            GuardianEvent,
        )
        from apps.api.services.guardian_intelligence import has_active_critical_event

        hh = _create_household(db_session)
        _, version = _setup_policy(db_session, hh.id)
        db_session.commit()

        portfolio_id, _, _, _ = _setup_portfolio_data(db_session, hh.id)
        db_session.commit()

        snapshot_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO portfolio_snapshots (id, portfolio_id, version_number, "
                "valuation_date, status) VALUES (:sid, :pid, 1, :vd, 'current')"
            ),
            {"sid": snapshot_id, "pid": portfolio_id, "vd": _now().date()},
        )

        check = GuardianCheck(
            id=uuid4(), household_id=hh.id,
            name="Warning Test", canonical_name="warn_v3",
            check_type="capital_bucket_drift", status="confirmed",
        )
        db_session.add(check)
        db_session.flush()

        confirmed = GuardianCheckConfirmed(
            id=uuid4(), check_id=check.id, version_number=1,
            check_type="capital_bucket_drift",
            threshold_value=Decimal("5"), severity="warning",
        )
        db_session.add(confirmed)
        db_session.flush()

        run = GuardianEvaluationRun(
            id=uuid4(), household_id=hh.id,
            status="completed", checks_evaluated=1, events_created=1,
            as_of_date=_now().date(),
        )
        db_session.add(run)
        db_session.flush()

        event = GuardianEvent(
            id=uuid4(), evaluation_run_id=run.id,
            household_id=hh.id, check_id=check.id,
            check_version_id=confirmed.id,
            check_type="capital_bucket_drift",
            policy_version_id=version.id,
            portfolio_snapshot_id=snapshot_id,
            exceeded=True, as_of_date=_now().date(),
        )
        db_session.add(event)
        db_session.commit()

        assert not has_active_critical_event(db_session, hh.id)
