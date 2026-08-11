"""Production Hardening API — Sprint 020."""

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.production_hardening import (
    AICalibrationService,
    ReliabilityService,
    SecurityAuditService,
    UXService,
)

router = APIRouter(prefix="/api/hardening", tags=["production-hardening"])


# ── AI Quality ───────────────────────────────────────────────────────


class CalibrateRequest(BaseModel):
    symbol: str
    confidence_scores: list[int]


@router.post("/ai/calibrate")
def calibrate_ai(body: CalibrateRequest):
    result = AICalibrationService.calibrate(
        body.symbol, body.confidence_scores,
    )
    return {
        "symbol": result.symbol,
        "runs": result.runs,
        "mean_confidence": result.mean_confidence,
        "std_deviation": round(result.std_deviation, 1),
        "is_consistent": result.is_consistent,
        "recommendation": result.recommendation,
    }


class VerifyClaimsRequest(BaseModel):
    claims: list[dict]


@router.post("/ai/verify")
def verify_claims(body: VerifyClaimsRequest):
    verifications = AICalibrationService.verify_claims(body.claims)
    return {
        "claims": [
            {"claim": v.claim, "status": v.status,
             "evidence_source": v.evidence_source}
            for v in verifications
        ],
        "summary": AICalibrationService.claim_summary(verifications),
    }


# ── Reliability ──────────────────────────────────────────────────────


@router.get("/reliability/health")
def provider_health():
    providers = ReliabilityService.provider_health()
    return {
        "providers": [
            {"name": p.provider, "status": p.status,
             "latency_ms": p.latency_ms, "healthy": p.is_healthy}
            for p in providers
        ],
        "all_healthy": all(p.is_healthy for p in providers),
    }


@router.get("/reliability/pipeline")
def pipeline_health():
    return ReliabilityService.pipeline_health_checks()


class CacheCheckRequest(BaseModel):
    cached_age_hours: float
    max_age_hours: float


@router.post("/reliability/cache")
def cache_check(body: CacheCheckRequest):
    return ReliabilityService.cache_validation(
        body.cached_age_hours, body.max_age_hours,
    )


# ── Security ─────────────────────────────────────────────────────────


@router.get("/security/audit")
def security_audit():
    results = SecurityAuditService.audit()
    return {
        "findings": [
            {"category": r.category, "status": r.status,
             "detail": r.detail, "recommendation": r.recommendation}
            for r in results
        ],
        "summary": SecurityAuditService.audit_summary(results),
    }


# ── UX ───────────────────────────────────────────────────────────────


@router.get("/ux/settings")
def ux_settings():
    ux = UXService.settings()
    return {
        "theme": ux.theme,
        "font_size": ux.font_size,
        "shortcuts": ux.shortcuts_list,
    }


@router.get("/ux/loading-states")
def loading_states():
    return UXService.loading_states()


@router.get("/ux/accessibility")
def accessibility():
    return UXService.accessibility_checklist()
