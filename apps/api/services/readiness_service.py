"""System Readiness — read-only bootstrap/setup status (M7-001).

Reports whether a fresh installation has completed the required setup
steps (migrations, owner key, household, prompt approval, providers,
governance). Read-only: no writes, no side effects, no secret exposure.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.health_service import (
    EXPECTED_MIGRATION_HEAD,
    HEALTHY,
    check_providers,
)


def _schema_at_head(session: Session) -> bool:
    row = session.execute(
        text("SELECT version_num FROM alembic_version"),
    ).fetchone()
    return bool(row) and row[0] == EXPECTED_MIGRATION_HEAD


def _owner_key_present(session: Session) -> bool:
    n = session.execute(text(
        "SELECT COUNT(*) FROM owner_api_keys WHERE revoked_at IS NULL"
    )).scalar() or 0
    return n > 0


def _household_created(session: Session) -> bool:
    n = session.execute(text(
        "SELECT COUNT(*) FROM household_profiles"
    )).scalar() or 0
    return n > 0


def _prompt_counts(session: Session) -> tuple[int, int]:
    active = session.execute(text(
        "SELECT COUNT(*) FROM prompt_templates WHERE status = 'active'"
    )).scalar() or 0
    draft = session.execute(text(
        "SELECT COUNT(*) FROM prompt_templates WHERE status = 'draft'"
    )).scalar() or 0
    return int(active), int(draft)


def _governance_ready() -> bool:
    """Governance layer (PermissionGate + PromptGovernor) is available."""
    try:
        from apps.api.services.permission_gate import PermissionGate
        from apps.api.services.prompt_governor import PromptGovernor

        PermissionGate()
        PromptGovernor()
        return True
    except Exception:
        return False


def _policy_published(session: Session) -> bool:
    """A published Investment Policy version exists (PE-003)."""
    from apps.api.repositories.households import get_current_household
    from apps.api.repositories.policies import (
        get_current_published,
        get_policy,
    )

    household = get_current_household(session)
    if household is None:
        return False
    policy = get_policy(session, household.id)
    if policy is None:
        return False
    return get_current_published(session, policy.id) is not None


def readiness_status(session: Session) -> dict:
    """Compute bootstrap readiness. Read-only, no side effects."""
    now = datetime.now(timezone.utc)

    schema_ok = _schema_at_head(session)
    owner_ok = _owner_key_present(session)
    household_ok = _household_created(session)
    active, draft = _prompt_counts(session)
    prompts_ok = active > 0 and draft == 0
    providers = check_providers(now)
    providers_ok = providers.status == HEALTHY
    gov_ok = _governance_ready()
    policy_ok = _policy_published(session)

    checks = {
        "schema_at_head": schema_ok,
        "owner_key_present": owner_ok,
        "household_created": household_ok,
        "prompts_approved": prompts_ok,
        "providers_configured": providers_ok,
        "governance_ready": gov_ok,
        "policy_published": policy_ok,
    }

    steps: list[str] = []
    if not schema_ok:
        steps.append("Run database migrations (alembic upgrade head)")
    if not gov_ok:
        steps.append("Governance layer unavailable — verify installation")
    if not owner_ok:
        steps.append(
            "Create an Owner API key (POST /api/auth/keys, or the "
            "bootstrap_key CLI in dev)",
        )
    if not household_ok:
        steps.append("Create the household profile (POST /api/household)")
    if not policy_ok:
        steps.append(
            "Create and publish an Investment Policy "
            "(/settings/investment-policy)",
        )
    if not prompts_ok:
        if draft > 0:
            steps.append(
                f"Approve {draft} draft prompt template(s) via "
                "POST /api/prompts/{id}/approve",
            )
        else:
            steps.append(
                "No active prompt templates — seed and approve prompt "
                "templates before the first research run",
            )
    if not providers_ok:
        missing = [n for n, s in providers.details.items() if s != "configured"]
        steps.append(
            "Configure provider credentials: "
            + (", ".join(missing) if missing else "all providers"),
        )

    return {
        "overall": "ready" if all(checks.values()) else "pending",
        "checks": checks,
        "remaining_steps": steps,
        "details": {
            "active_prompts": active,
            "draft_prompts": draft,
            "providers": providers.details,
        },
    }
