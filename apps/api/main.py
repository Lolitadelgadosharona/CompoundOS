from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routers.decisions import router as decisions_router
from apps.api.routers.guardian import router as guardian_router
from apps.api.routers.households import router as households_router
from apps.api.routers.policies import router as policies_router
from apps.api.routers.portfolios import router as portfolios_router

app = FastAPI(title="CompoundOS API", version="0.1.0")

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


app.include_router(households_router)
app.include_router(policies_router)
app.include_router(decisions_router)
app.include_router(portfolios_router)
app.include_router(guardian_router)
