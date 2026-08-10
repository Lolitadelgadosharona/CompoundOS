"""Tests for Sprint 010 Slice C — Wealth Dashboard + Learning Loop."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0027_evidence_knowledge"
_PORTFOLIO_CACHE: dict = {}


def _now():
    return datetime.now(timezone.utc)


def _create_household(session, name="Test"):
    from apps.api.models import HouseholdProfile
    hh = HouseholdProfile(id=uuid4(), household_name=name, base_currency="USD")
    session.add(hh)
    session.flush()
    return hh


def _setup_position(session, household_id, market_value=Decimal("50000"),
                    bucket="CORE", currency="USD"):
    from apps.api.models import (
        Account,
        Asset,
        Portfolio,
        PortfolioDraft,
        Position,
    )
    key = str(household_id)
    if key not in _PORTFOLIO_CACHE:
        pf = Portfolio(id=uuid4(), household_id=household_id, status="draft")
        session.add(pf)
        session.flush()
        draft = PortfolioDraft(
            portfolio_id=pf.id, expected_revision=1,
            valuation_date=_now().date(),
        )
        session.add(draft)
        session.flush()
        _PORTFOLIO_CACHE[key] = pf.id
    pfid = _PORTFOLIO_CACHE[key]
    acct = Account(id=uuid4(), portfolio_id=pfid, name="Test",
                   account_type="brokerage", capital_bucket=bucket,
                   currency=currency)
    session.add(acct)
    session.flush()
    asset = Asset(id=uuid4(), name="Test Asset", asset_type="STOCK",
                  currency=currency)
    session.add(asset)
    session.flush()
    pos = Position(
        id=uuid4(), account_id=acct.id, asset_id=asset.id,
        quantity=Decimal("100"), quantity_source="provider_reported",
        avg_cost=Decimal("500"), avg_cost_currency=currency,
        market_price=Decimal("500"), market_price_currency=currency,
        market_value=market_value, observed_at=_now(),
        source="csv", is_latest=True,
    )
    session.add(pos)
    session.flush()


class TestMigration:
    def test_decision_reviews_table_exists(self, db_session):
        db_session.execute(text("SELECT 1 FROM decision_reviews LIMIT 0"))

    def test_snapshot_new_columns(self, db_session):
        """review_30d, review_90d, review_1yr, review_outcome exist."""
        cols = db_session.execute(text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'decision_confirmed_snapshots'"
            " AND column_name IN ('review_30d','review_90d','review_1yr','review_outcome')"
        )).fetchall()
        assert len(cols) == 4

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


class TestDashboard:
    def test_dashboard_net_worth(self, db_session):
        from apps.api.services.dashboard_service import build_dashboard
        hh = _create_household(db_session)
        db_session.commit()
        _setup_position(db_session, hh.id, market_value=Decimal("100000"))
        db_session.commit()
        dash = build_dashboard(db_session, hh.id)
        assert Decimal(dash.net_worth.total_value) > 0

    def test_dashboard_net_worth_empty(self, db_session):
        from apps.api.services.dashboard_service import build_dashboard
        hh = _create_household(db_session)
        db_session.commit()
        dash = build_dashboard(db_session, hh.id)
        assert dash.net_worth.total_value == "0.00"

    def test_dashboard_allocation(self, db_session):
        from apps.api.services.dashboard_service import build_dashboard
        hh = _create_household(db_session)
        db_session.commit()
        _setup_position(db_session, hh.id, bucket="CORE", market_value=Decimal("70000"))
        _setup_position(db_session, hh.id, bucket="EXPLORATION", market_value=Decimal("30000"))
        db_session.commit()
        dash = build_dashboard(db_session, hh.id)
        assert len(dash.allocation.by_bucket) >= 2

    def test_dashboard_ideas_summary_empty(self, db_session):
        from apps.api.services.dashboard_service import build_dashboard
        hh = _create_household(db_session)
        db_session.commit()
        dash = build_dashboard(db_session, hh.id)
        assert dash.ideas.total == 0


class TestLearningLoop:
    def test_no_idea_not_high_impact(self, db_session):
        from apps.api.services.dashboard_service import is_high_impact
        hh = _create_household(db_session)
        db_session.commit()
        assert not is_high_impact(db_session, None, hh.id)

    def test_high_impact_no_positions(self, db_session):
        from apps.api.services.dashboard_service import is_high_impact
        hh = _create_household(db_session)
        db_session.commit()
        assert not is_high_impact(db_session, uuid4(), hh.id)

    def test_low_impact_empty_portfolio(self, db_session):
        from apps.api.services.dashboard_service import is_high_impact
        hh = _create_household(db_session)
        db_session.commit()
        assert not is_high_impact(db_session, uuid4(), hh.id)
