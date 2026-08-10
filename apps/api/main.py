from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.mutation_gate import mutation_gate
from apps.api.routers.automation import router as automation_router
from apps.api.routers.backup import router as backup_router
from apps.api.routers.committee import router as committee_router
from apps.api.routers.decisions import router as decisions_router
from apps.api.routers.guardian import router as guardian_router
from apps.api.routers.health import router as health_router
from apps.api.routers.households import router as households_router
from apps.api.routers.imports import router as imports_router
from apps.api.routers.notifications import router as notifications_router
from apps.api.routers.policies import router as policies_router
from apps.api.routers.portfolios import router as portfolios_router

app = FastAPI(title="CompoundOS API", version="0.1.0")

app.middleware("http")(mutation_gate)

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
