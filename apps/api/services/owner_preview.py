"""Explicit local-only preview boundary; never a production fallback."""

import os
from urllib.parse import urlparse


def enabled():
    return os.getenv("COMPOUNDOS_PREVIEW_MODE", "").lower() == "true"


def validate_environment():
    url = urlparse(os.getenv("DATABASE_URL", ""))
    preview_db = url.path.lstrip("/") == "compoundos_owner_preview_test"
    if enabled() and (os.getenv("ENVIRONMENT") != "test" or not preview_db):
        raise RuntimeError("Owner Preview requires test environment and dedicated preview database")
    if preview_db and not enabled():
        raise RuntimeError("Preview database cannot be opened in LIVE mode")


def qualities():
    return {"OBSERVED", "DELAYED", "DEMO"} if enabled() else {"OBSERVED", "DELAYED"}


def require_preview():
    validate_environment()
    if not enabled():
        raise RuntimeError("Demo provider is unavailable outside Owner Preview")


def data_mode():
    return "SIMULATED" if enabled() else "LIVE"
