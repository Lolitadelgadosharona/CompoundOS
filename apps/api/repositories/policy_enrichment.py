"""Repository layer for Sprint 009 Slice B — Investment Policy Enrichment.

SQLAlchemy queries for policy_capital_buckets and policy_rules.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.api.models import PolicyCapitalBucket, PolicyRule

# ═══════════════════════════════════════════════════════════════════════
# Capital Buckets
# ═══════════════════════════════════════════════════════════════════════


def list_draft_buckets(
    session: Session, draft_id: UUID, *, for_update: bool = False,
) -> list[PolicyCapitalBucket]:
    statement = (
        select(PolicyCapitalBucket)
        .where(PolicyCapitalBucket.draft_id == draft_id)
        .order_by(PolicyCapitalBucket.sort_order.asc())
    )
    if for_update:
        statement = statement.with_for_update()
    return list(session.scalars(statement))


def list_version_buckets(
    session: Session, version_id: UUID,
) -> list[PolicyCapitalBucket]:
    statement = (
        select(PolicyCapitalBucket)
        .where(PolicyCapitalBucket.version_id == version_id)
        .order_by(PolicyCapitalBucket.sort_order.asc())
    )
    return list(session.scalars(statement))


def replace_draft_buckets(
    session: Session, draft_id: UUID, buckets: list[dict],
) -> list[PolicyCapitalBucket]:
    session.execute(
        delete(PolicyCapitalBucket).where(
            PolicyCapitalBucket.draft_id == draft_id,
        )
    )
    rows = [
        PolicyCapitalBucket(id=uuid4(), draft_id=draft_id, **item)
        for item in buckets
    ]
    session.add_all(rows)
    session.flush()
    return rows


def create_version_bucket(
    session: Session, version_id: UUID, **kwargs,
) -> PolicyCapitalBucket:
    bucket = PolicyCapitalBucket(id=uuid4(), version_id=version_id, **kwargs)
    session.add(bucket)
    session.flush()
    return bucket


# ═══════════════════════════════════════════════════════════════════════
# Policy Rules
# ═══════════════════════════════════════════════════════════════════════


def list_draft_rules(
    session: Session, draft_id: UUID, *, for_update: bool = False,
) -> list[PolicyRule]:
    statement = (
        select(PolicyRule)
        .where(PolicyRule.draft_id == draft_id)
        .order_by(PolicyRule.sort_order.asc())
    )
    if for_update:
        statement = statement.with_for_update()
    return list(session.scalars(statement))


def list_version_rules(
    session: Session, version_id: UUID,
) -> list[PolicyRule]:
    statement = (
        select(PolicyRule)
        .where(PolicyRule.version_id == version_id)
        .order_by(PolicyRule.sort_order.asc())
    )
    return list(session.scalars(statement))


def replace_draft_rules(
    session: Session, draft_id: UUID, rules: list[dict],
) -> list[PolicyRule]:
    session.execute(
        delete(PolicyRule).where(
            PolicyRule.draft_id == draft_id,
        )
    )
    rows = [
        PolicyRule(id=uuid4(), draft_id=draft_id, **item)
        for item in rules
    ]
    session.add_all(rows)
    session.flush()
    return rows


def create_version_rule(
    session: Session, version_id: UUID, **kwargs,
) -> PolicyRule:
    rule = PolicyRule(id=uuid4(), version_id=version_id, **kwargs)
    session.add(rule)
    session.flush()
    return rule
