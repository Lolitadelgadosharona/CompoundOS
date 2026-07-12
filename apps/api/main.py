from fastapi import FastAPI

app = FastAPI(title="CompoundOS API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}
