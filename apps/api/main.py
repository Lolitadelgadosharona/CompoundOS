from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.mutation_gate import mutation_gate
from apps.api.routers.auth import router as auth_router
from apps.api.routers.automation import router as automation_router
from apps.api.routers.backup import router as backup_router
from apps.api.routers.committee import router as committee_router
from apps.api.routers.committee_bridge import router as committee_bridge_router
from apps.api.routers.dashboard import router as dashboard_router
from apps.api.routers.decisions import router as decisions_router
from apps.api.routers.guardian import router as guardian_router
from apps.api.routers.health import router as health_router
from apps.api.routers.households import router as households_router
from apps.api.routers.imports import router as imports_router
from apps.api.routers.notifications import router as notifications_router
from apps.api.routers.policies import router as policies_router
from apps.api.routers.portfolios import router as portfolios_router
from apps.api.routers.research import router as research_router
from apps.api.routers.research_workflow import router as research_workflow_router
from apps.api.routers.dashboard_data import router as dashboard_data_router
from apps.api.routers.daily_ops import router as daily_ops_router
from apps.api.routers.intelligence import router as intelligence_router
from apps.api.routers.portfolio_upgrade import router as portfolio_upgrade_router
from apps.api.routers.investment_os import router as investment_os_router
from apps.api.routers.production import router as production_router
from apps.api.routers.real_ops import router as real_ops_router
from apps.api.routers.scale import router as scale_router
from apps.api.routers.household import router as household_router

app = FastAPI(title="CompoundOS API", version="0.1.0")

app.middleware("http")(mutation_gate)


# Sprint 010 Slice D — Global auth middleware (H1)
# Applied to ALL requests. Bypasses only health endpoints and dev/test env.
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    import hashlib
    import os

    path = request.url.path

    # PUBLIC: health endpoints never require auth
    if path in ("/health", "/api/health"):
        return await call_next(request)

    env = os.getenv("ENVIRONMENT", "").strip().lower()
    if env in ("development", "test"):
        request.state.role = "owner"
        return await call_next(request)

    # All other endpoints require X-API-Key
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "X-API-Key header required"},
        )

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    from sqlalchemy import text as _t

    from apps.api.database import SessionLocal
    db = SessionLocal()
    try:
        row = db.execute(
            _t(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": key_hash},
        ).fetchone()
        if row is None:
            db.execute(
                _t(
                    "INSERT INTO audit_log"
                    " (id, event_type, actor_id, action, outcome, occurred_at)"
                    " VALUES (:id, 'authentication.failure', :aid, :act,"
                    " 'failure', :now)"
                ),
                {
                    "id": __import__("uuid").uuid4(),
                    "aid": key_hash[:12],
                    "act": path,
                    "now": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc,
                    ),
                },
            )
            db.commit()
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
            )
        db.execute(
            _t(
                "UPDATE owner_api_keys SET last_used_at = NOW()"
                " WHERE id = :kid"
            ),
            {"kid": row[0]},
        )
        db.execute(
            _t(
                "INSERT INTO audit_log"
                " (id, event_type, actor_id, actor_role, action, outcome,"
                " occurred_at)"
                " VALUES (:id, 'authentication.success', :aid, 'owner',"
                " :act, 'success', :now)"
            ),
            {
                "id": __import__("uuid").uuid4(),
                "aid": key_hash[:12],
                "act": path,
                "now": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc,
                ),
            },
        )
        db.commit()
        request.state.role = "owner"
    finally:
        db.close()

    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation details without echoing sensitive request values."""
    details = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


app.include_router(automation_router)
app.include_router(households_router)
app.include_router(policies_router)
app.include_router(decisions_router)
app.include_router(portfolios_router)
app.include_router(guardian_router)
app.include_router(committee_router)
app.include_router(backup_router)
app.include_router(health_router)
app.include_router(notifications_router)
app.include_router(imports_router)
app.include_router(committee_bridge_router)
app.include_router(dashboard_router)
app.include_router(research_router)
app.include_router(research_workflow_router)
app.include_router(dashboard_data_router)
app.include_router(daily_ops_router)
app.include_router(intelligence_router)
app.include_router(portfolio_upgrade_router)
app.include_router(investment_os_router)
app.include_router(production_router)
app.include_router(real_ops_router)
app.include_router(scale_router)
app.include_router(household_router)
app.include_router(auth_router)
