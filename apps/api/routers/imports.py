"""Import router — manual CSV import endpoints.

Sprint 009 Slice D — Manual Import + Data Source Foundation.
Owner authentication only. No broker connections.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.import_schemas import (
    DataSourceCreate,
    DataSourceResponse,
    ImportResponse,
)
from apps.api.repositories.portfolio_foundation import (
    create_data_source,
    list_active_data_sources,
)
from apps.api.services.import_service import (
    import_cash_balances_from_csv,
    import_positions_from_csv,
    import_transactions_from_csv,
)

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _read_csv(file: UploadFile) -> str:
    """Read and validate an uploaded CSV file."""
    content_bytes = file.file.read()
    if len(content_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")
    return content_bytes.decode("utf-8-sig")  # handle BOM


# ═══════════════════════════════════════════════════════════════════════
# Manual CSV Import
# ═══════════════════════════════════════════════════════════════════════


@router.post("/positions", response_model=ImportResponse)
def import_positions(
    file: UploadFile = File(...),
    source_key: str = "default_csv",
    session: Session = Depends(get_session),
) -> ImportResponse:
    """Import positions from a CSV file. All-or-nothing transaction."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload must be a CSV file")
    csv_content = _read_csv(file)
    try:
        with session.begin():
            return import_positions_from_csv(session, csv_content, source_key)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/transactions", response_model=ImportResponse)
def import_transactions(
    file: UploadFile = File(...),
    source_key: str = "default_csv",
    session: Session = Depends(get_session),
) -> ImportResponse:
    """Import transactions from a CSV file. All-or-nothing transaction."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload must be a CSV file")
    csv_content = _read_csv(file)
    try:
        with session.begin():
            return import_transactions_from_csv(session, csv_content, source_key)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/cash-balances", response_model=ImportResponse)
def import_cash_balances(
    file: UploadFile = File(...),
    source_key: str = "default_csv",
    session: Session = Depends(get_session),
) -> ImportResponse:
    """Import cash balances from a CSV file. All-or-nothing transaction."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload must be a CSV file")
    csv_content = _read_csv(file)
    try:
        with session.begin():
            return import_cash_balances_from_csv(session, csv_content, source_key)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


# ═══════════════════════════════════════════════════════════════════════
# Data Sources
# ═══════════════════════════════════════════════════════════════════════


@router.get("/sources", response_model=list[DataSourceResponse])
def list_sources(
    session: Session = Depends(get_session),
) -> list[DataSourceResponse]:
    """List active data sources."""
    sources = list_active_data_sources(session)
    return [
        DataSourceResponse(
            source_key=s.source_key,
            source_type=s.source_type,
            display_name=s.display_name,
            is_active=s.is_active,
            last_import_at=s.last_import_at,
            created_at=s.created_at,
        )
        for s in sources
    ]


@router.post("/sources", response_model=DataSourceResponse)
def create_source(
    body: DataSourceCreate,
    session: Session = Depends(get_session),
) -> DataSourceResponse:
    """Register a new data source."""
    source = create_data_source(
        session,
        source_key=body.source_key,
        source_type=body.source_type,
        display_name=body.display_name,
    )
    return DataSourceResponse(
        source_key=source.source_key,
        source_type=source.source_type,
        display_name=source.display_name,
        is_active=source.is_active,
        last_import_at=source.last_import_at,
        created_at=source.created_at,
    )
