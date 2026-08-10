"""Pydantic schemas for Sprint 010 Slice C — Wealth Dashboard + Learning Loop."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ── Dashboard ─────────────────────────────────────────────────────────


class AllocationEntry(BaseModel):
    value: str
    percentage: str


class NetWorth(BaseModel):
    total_value: str
    by_currency: dict[str, str] = Field(default_factory=dict)
    by_account_type: dict[str, str] = Field(default_factory=dict)
    unconverted_currencies: list[str] = Field(default_factory=list)
    as_of: datetime


class Allocation(BaseModel):
    by_asset_class: dict[str, AllocationEntry] = Field(default_factory=dict)
    by_bucket: dict[str, AllocationEntry] = Field(default_factory=dict)
    by_currency: dict[str, AllocationEntry] = Field(default_factory=dict)


class BucketDrift(BaseModel):
    bucket_name: str
    target_pct: str
    actual_pct: str
    drift_pct: str
    severity: str


class RuleViolation(BaseModel):
    rule_type: str
    description: str
    severity: str
    detected_at: datetime


class PolicyCompliance(BaseModel):
    overall_status: str
    bucket_drifts: list[BucketDrift] = Field(default_factory=list)
    rule_violations: list[RuleViolation] = Field(default_factory=list)


class RiskSummary(BaseModel):
    concentration_risk: str
    active_guardian_events: int
    newest_guardian_event_at: Optional[datetime] = None


class PendingDecision(BaseModel):
    decision_id: UUID
    title: str
    investment_idea_id: Optional[UUID] = None
    status: str
    created_at: datetime


class IdeaSummary(BaseModel):
    total: int
    draft: int
    under_review: int
    approved: int
    rejected: int


class ActivityItem(BaseModel):
    type: str
    title: str
    description: str
    occurred_at: datetime


class ActivityFeed(BaseModel):
    items: list[ActivityItem] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    net_worth: NetWorth
    allocation: Allocation
    policy_compliance: PolicyCompliance
    risks: RiskSummary
    pending_decisions: list[PendingDecision] = Field(default_factory=list)
    ideas: IdeaSummary
    recent_activity: ActivityFeed


# ── Learning Loop ─────────────────────────────────────────────────────


class DecisionReviewResponse(BaseModel):
    id: UUID
    decision_id: UUID
    investment_idea_id: Optional[UUID] = None
    review_type: str
    scheduled_at: date
    completed_at: Optional[datetime] = None
    outcome_notes: Optional[str] = None
    actual_return_pct: Optional[str] = None
    policy_compliant: Optional[bool] = None
    lessons_learned: Optional[str] = None
    created_at: datetime
    updated_at: datetime
