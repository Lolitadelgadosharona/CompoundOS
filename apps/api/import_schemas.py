"""Pydantic schemas for Sprint 009 Slice D — Manual Import + Data Source Foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImportWarning(BaseModel):
    code: str
    row_index: int
    column: str
    message: str


class ImportError_(BaseModel):
    row_index: int
    column: str
    message: str


class ImportSummary(BaseModel):
    rows_processed: int = 0
    positions_created: int = 0
    positions_updated: int = 0
    transactions_created: int = 0
    transactions_skipped: int = 0
    cash_balances_created: int = 0
    cash_balances_updated: int = 0
    assets_resolved: int = 0
    assets_created: int = 0
    errors: int = 0
    warnings: int = 0


class ImportResponse(BaseModel):
    source_key: str
    imported_at: datetime
    summary: ImportSummary
    warnings: list[ImportWarning] = Field(default_factory=list)
    errors: list[ImportError_] = Field(default_factory=list)


class DataSourceCreate(BaseModel):
    source_key: str = Field(..., min_length=1, max_length=100)
    source_type: str = Field(..., pattern=r"^(csv|manual|broker|bank)$")
    display_name: Optional[str] = None


class DataSourceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class DataSourceResponse(BaseModel):
    source_key: str
    source_type: str
    display_name: Optional[str] = None
    is_active: bool
    last_import_at: Optional[datetime] = None
    created_at: datetime
