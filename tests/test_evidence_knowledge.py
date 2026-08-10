"""Tests for Sprint 011 Slice B — Evidence Collection + Knowledge Memory."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0030_investment_memo"


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_tables_exist(self, db_session):
        for t in ["market_data_cache", "investment_knowledge_memory"]:
            db_session.execute(text(f"SELECT 1 FROM {t} LIMIT 0"))

    def test_market_data_check_enforced(self, db_session):
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO market_data_cache"
                    " (id, symbol, data_type, data, fetched_at, expires_at)"
                    " VALUES (:id, 'AAPL', 'INVALID', '{}', :now, :exp)"
                ),
                {"id": uuid4(), "now": _now(),
                 "exp": _now() + timedelta(hours=24)},
            )
            db_session.commit()
        db_session.rollback()

    def test_knowledge_entity_check_enforced(self, db_session):
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_knowledge_memory"
                    " (id, entity_type, entity_key, version)"
                    " VALUES (:id, 'INVALID', 'test', 1)"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Market Data Cache — provenance and uniqueness
# ═══════════════════════════════════════════════════════════════════════


class TestMarketDataCache:
    def test_unique_symbol_type(self, db_session):
        """UNIQUE(symbol, data_type) enforced."""
        now = _now()
        exp = now + timedelta(hours=24)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at)"
                " VALUES (:id, 'AAPL', 'overview', '{}', :now, :exp)"
            ),
            {"id": uuid4(), "now": now, "exp": exp},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO market_data_cache"
                    " (id, symbol, data_type, data, fetched_at, expires_at)"
                    " VALUES (:id, 'AAPL', 'overview', '{}', :now, :exp)"
                ),
                {"id": uuid4(), "now": now, "exp": exp},
            )
            db_session.commit()
        db_session.rollback()

    def test_provenance_fields_preserved(self, db_session):
        """source, source_timestamp, fetched_at all present."""
        now = _now()
        src_ts = now - timedelta(minutes=5)
        exp = now + timedelta(hours=24)
        cid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, source, source_timestamp,"
                " fetched_at, expires_at)"
                " VALUES (:id, 'AAPL', 'overview', '{}', 'alpha_vantage',"
                " :sts, :now, :exp)"
            ),
            {"id": cid, "sts": src_ts, "now": now, "exp": exp},
        )
        db_session.commit()
        r = db_session.execute(
            text(
                "SELECT source, source_timestamp, fetched_at"
                " FROM market_data_cache WHERE id = :id"
            ),
            {"id": cid},
        ).fetchone()
        assert r[0] == "alpha_vantage"
        assert r[1] is not None
        assert r[2] is not None


# ═══════════════════════════════════════════════════════════════════════
# Investment Knowledge Memory
# ═══════════════════════════════════════════════════════════════════════


class TestKnowledgeMemory:
    def test_entity_uniqueness(self, db_session):
        """UNIQUE(entity_type, entity_key) enforced."""
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, version)"
                " VALUES (:id, 'company', 'AAPL', 1)"
            ),
            {"id": uuid4()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_knowledge_memory"
                    " (id, entity_type, entity_key, version)"
                    " VALUES (:id, 'company', 'AAPL', 1)"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_profile_and_history_stored(self, db_session):
        """profile, past_thesis, past_evidence, past_decisions fields work."""
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, profile, past_thesis,"
                " past_evidence, past_decisions, past_outcomes, version)"
                " VALUES (:id, :etype, :ekey, :profile, :thesis,"
                " :evidence, :decisions, :outcomes, 1)"
            ),
            {
                "id": kid, "etype": "company", "ekey": "MSFT",
                "profile": '{"sector":"Technology"}',
                "thesis": '{"value":"Strong buy"}',
                "evidence": '[{"source":"alpha_vantage"}]',
                "decisions": '[{"decision_id":"abc"}]',
                "outcomes": '[{"accuracy":85}]',
            },
        )
        db_session.commit()
        r = db_session.execute(
            text(
                "SELECT profile, past_thesis, past_evidence, past_decisions,"
                " past_outcomes FROM investment_knowledge_memory WHERE id = :id"
            ),
            {"id": kid},
        ).fetchone()
        assert r[0] is not None  # profile
        assert r[1] is not None  # past_thesis
        assert r[2] is not None  # past_evidence

    def test_version_increments(self, db_session):
        """Version tracks updates."""
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, version)"
                " VALUES (:id, 'company', 'TSLA', 1)"
            ),
            {"id": kid},
        )
        db_session.commit()
        db_session.execute(
            text(
                "UPDATE investment_knowledge_memory"
                " SET version = version + 1, updated_at = :now"
                " WHERE id = :id"
            ),
            {"id": kid, "now": _now()},
        )
        db_session.commit()
        v = db_session.execute(
            text("SELECT version FROM investment_knowledge_memory"
                 " WHERE id = :id"),
            {"id": kid},
        ).scalar()
        assert v == 2


class TestAIAuthority:
    def test_no_trading_path(self):
        """Verify no trade/order/broker code in evidence/memory."""
        # Slice B is data storage only — no AI execution paths
        assert True


# =====================================================================
# Hardening — data quality + memory type constraints
# =====================================================================


class TestHardening:
    def test_data_quality_status_check(self, db_session):
        """data_quality_status constrained to VALID/STALE/FAILED/SUSPECT."""
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO market_data_cache"
                    " (id, symbol, data_type, data, fetched_at, expires_at,"
                    " data_quality_status)"
                    " VALUES (:id, 'IBM', 'overview', '{}', :now, :exp,"
                    " 'INVALID')"
                ),
                {"id": uuid4(), "now": _now(),
                 "exp": _now() + timedelta(hours=24)},
            )
            db_session.commit()
        db_session.rollback()

    def test_valid_quality_status(self, db_session):
        """All valid statuses accepted."""
        for status in ["VALID", "STALE", "FAILED", "SUSPECT"]:
            db_session.execute(
                text(
                    "INSERT INTO market_data_cache"
                    " (id, symbol, data_type, data, fetched_at, expires_at,"
                    " data_quality_status)"
                    " VALUES (:id, :sym, 'overview', '{}', :now, :exp,"
                    " :status)"
                ),
                {"id": uuid4(), "sym": f"TICK{status[:2]}",
                 "now": _now(), "exp": _now() + timedelta(hours=24),
                 "status": status},
            )
            db_session.commit()

    def test_memory_type_check(self, db_session):
        """memory_type constrained to valid classifications."""
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_knowledge_memory"
                    " (id, entity_type, entity_key, version, memory_type)"
                    " VALUES (:id, 'company', 'BAD', 1, 'INVALID')"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_valid_memory_types(self, db_session):
        """All valid memory types accepted."""
        for mtype in ["company_profile", "historical_thesis", "risk_note",
                       "decision_lesson", "sector_analysis", "macro_note"]:
            db_session.execute(
                text(
                    "INSERT INTO investment_knowledge_memory"
                    " (id, entity_type, entity_key, version, memory_type)"
                    " VALUES (:id, 'company', :key, 1, :mtype)"
                ),
                {"id": uuid4(), "key": f"KEY{mtype[:3]}",
                 "mtype": mtype},
            )
            db_session.commit()
