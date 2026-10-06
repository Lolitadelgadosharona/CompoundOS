"""Published governance must survive ordinary draft cloning and publication."""

from decimal import Decimal

import pytest

from apps.api.models import InvestmentPolicyDraftAllocation
from apps.api.policy_schemas import CreatePolicyDraftRequest, PublishPolicyDraftRequest
from apps.api.repositories import policy_enrichment as repo
from apps.api.services.policies import create_new_draft, discard_draft, publish_draft
from tests.test_policy_enrichment import _create_policy_setup, _create_published_version

pytestmark = pytest.mark.postgres


def test_publish_preserves_exact_draft_buckets_rules(db_session):
    _, _, draft = _create_policy_setup(db_session)
    draft.objectives = "Synthetic governance preservation"
    draft.time_horizon = "long"
    draft.decision_process = "Owner approval"
    db_session.add(
        InvestmentPolicyDraftAllocation(
            draft_id=draft.id,
            asset_class_name="ETF",
            normalized_asset_class_name="etf",
            target_percentage=Decimal(100),
            sort_order=0,
        )
    )
    buckets = [
        dict(
            bucket_name="CORE",
            target_pct=Decimal(70),
            min_pct=Decimal(60),
            max_pct=Decimal(80),
            description="Preserve bounds",
            sort_order=0,
        ),
        dict(
            bucket_name="EXPLORATION",
            target_pct=Decimal(30),
            min_pct=Decimal(20),
            max_pct=Decimal(40),
            description="Preserve smaller bucket",
            sort_order=1,
        ),
    ]
    rules = [
        dict(
            rule_type="max_single_position_pct",
            rule_value="15",
            severity="critical",
            enabled=True,
            description="Synthetic tighter bound",
            sort_order=0,
        ),
        dict(
            rule_type="custom",
            rule_value="opaque-owner-rule",
            severity="warning",
            enabled=False,
            description="Disabled flag preserved",
            sort_order=1,
        ),
    ]
    repo.replace_draft_buckets(db_session, draft.id, buckets)
    repo.replace_draft_rules(db_session, draft.id, rules)
    db_session.commit()
    version, _ = publish_draft(
        db_session,
        PublishPolicyDraftRequest(
            expected_revision=draft.revision,
            confirmation=True,
        ),
    )
    saved_buckets = repo.list_version_buckets(db_session, version.id)
    saved_rules = repo.list_version_rules(db_session, version.id)
    assert [{k: getattr(x, k) for k in b} for x, b in zip(saved_buckets, buckets)] == buckets
    assert len(saved_buckets) == len(buckets)
    assert [{k: getattr(x, k) for k in r} for x, r in zip(saved_rules, rules)] == rules
    assert len(saved_rules) == len(rules)
    assert version.sealed_at is not None
    assert not repo.list_draft_rules(db_session, draft.id)


def test_clone_carries_published_governance_without_changing_original(db_session):
    _, policy, draft = _create_policy_setup(db_session)
    version, core, rule = _create_published_version(db_session, policy.id)
    db_session.commit()
    discard_draft(db_session, draft.revision)
    new, _ = create_new_draft(db_session, CreatePolicyDraftRequest(source_version_id=version.id))
    saved_buckets = repo.list_draft_buckets(db_session, new.id)
    saved_rules = repo.list_draft_rules(db_session, new.id)
    assert len(saved_buckets) == 1 and len(saved_rules) == 1
    assert {(x.bucket_name, x.target_pct, x.min_pct, x.max_pct) for x in saved_buckets} == {
        (x.bucket_name, x.target_pct, x.min_pct, x.max_pct) for x in [core]
    }
    assert saved_rules[0].rule_type == rule.rule_type
    assert saved_rules[0].rule_value == rule.rule_value
    assert saved_rules[0].severity == rule.severity and saved_rules[0].enabled == rule.enabled
    assert version.status == "published" and version.sealed_at is not None


def test_personal_setup_does_not_discard_existing_draft_governance(db_session):
    from apps.api.policy_schemas import PersonalPolicySetupRequest
    from apps.api.services.policies import setup_personal_policy

    _, _, draft = _create_policy_setup(db_session)
    rules = [
        dict(
            rule_type=name,
            rule_value=value,
            severity="critical",
            enabled=True,
            description="Synthetic preservation only",
            sort_order=i,
        )
        for i, (name, value) in enumerate(
            [("max_single_position_pct", "20"), ("min_cash_reserve_pct", "0")]
        )
    ]
    repo.replace_draft_rules(db_session, draft.id, rules)
    db_session.commit()
    version = setup_personal_policy(
        db_session,
        PersonalPolicySetupRequest(
            investment_goal="Synthetic governance preservation",
            risk_preference="Moderate",
            investment_horizon="10+ years",
            max_single_position_pct=20,
            min_cash_pct=0,
            principles="Preserve explicitly supplied limits",
        ),
    )
    saved = repo.list_version_rules(db_session, version.id)
    assert [(r.rule_type, r.rule_value, r.enabled, r.severity) for r in saved] == [
        (r["rule_type"], r["rule_value"], r["enabled"], r["severity"]) for r in rules
    ]
    assert version.sealed_at is not None
