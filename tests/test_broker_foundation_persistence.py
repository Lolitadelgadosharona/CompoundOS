# ruff: noqa: F811
"""Resolver/approval boundary tests in new isolated PostgreSQL only."""

import pytest

from apps.api.services.broker_foundation import CanonicalResolver, StagingStore
from apps.api.services.instrument_resolver import Instrument
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup


@pytest.mark.postgres
def test_broker_identity_uses_existing_canonical_mapping(db_session):
    i = Instrument("BRK.B", "Berkshire class B", "NYSE", "STOCK", "USD", "synthetic", "BRK-B")
    resolver = CanonicalResolver(db_session)
    first = resolver(i)
    assert resolver(i) == first
    from apps.api.models import Asset

    assert db_session.get(Asset, first).symbol == "BRK.B"


@pytest.mark.postgres
def test_actual_approval_does_not_call_broker_adapter(db_session, setup, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Approval entered broker adapter boundary")

    monkeypatch.setattr(StagingStore, "sync", forbidden)
    from tests.test_launch_v1 import test_approval_journal_audit_manual_only

    test_approval_journal_audit_manual_only(db_session, setup)
