"""Validation rules for manual financial data import.

Sprint 009 Slice D — Manual Import + Data Source Foundation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from apps.api.importers.csv_parser import (
    CURRENCY_RE,
    VALID_ASSET_TYPES,
    VALID_TRANSACTION_TYPES,
)


class Severity:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    row_index: int
    column: str
    message: str
    severity: str = Severity.ERROR


@dataclass
class ValidationResult:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def error(self, row_index: int, column: str, message: str) -> None:
        self.errors.append(ValidationIssue(row_index, column, message, Severity.ERROR))

    def warning(self, row_index: int, column: str, message: str) -> None:
        self.warnings.append(ValidationIssue(row_index, column, message, Severity.WARNING))


def validate_position_row(
    row: dict[str, str], row_index: int, result: ValidationResult,
) -> None:
    """Validate a single position CSV row."""
    # Required fields
    for col in ["source_record_id", "account_provider_id", "symbol", "currency",
                "quantity", "observed_at"]:
        if not row.get(col):
            result.error(row_index, col, f"Missing required column: {col}")

    # currency format
    currency = row.get("currency", "")
    if currency and not CURRENCY_RE.match(currency):
        result.error(row_index, "currency", f"Invalid currency: {currency!r}")

    # asset_type
    asset_type = row.get("asset_type", "")
    if asset_type and asset_type not in VALID_ASSET_TYPES:
        result.error(row_index, "asset_type", f"Invalid asset_type: {asset_type!r}")

    # quantity >= 0
    qty_str = row.get("quantity")
    if qty_str:
        try:
            qty = Decimal(qty_str.strip())
            if qty < 0:
                result.error(row_index, "quantity", "Quantity must be >= 0")
        except Exception:
            result.error(row_index, "quantity", f"Invalid quantity: {qty_str!r}")

    # decimals
    for col in ["avg_cost", "market_price"]:
        val = row.get(col)
        if val and val.strip():
            try:
                Decimal(val.strip())
            except Exception:
                result.error(row_index, col, f"Invalid decimal: {val!r}")

    # observed_at
    obs_str = row.get("observed_at")
    if obs_str:
        try:
            from apps.api.importers.csv_parser import parse_csv_datetime
            obs = parse_csv_datetime(obs_str)
            if obs and obs > datetime.now(timezone.utc):
                result.warning(row_index, "observed_at", "observed_at is in the future")
        except ValueError as exc:
            result.error(row_index, "observed_at", str(exc))

    # isin format
    isin = row.get("isin", "")
    if isin and len(isin) != 12:
        result.warning(row_index, "isin", f"ISIN should be 12 chars, got {len(isin)}")


def validate_transaction_row(
    row: dict[str, str], row_index: int, result: ValidationResult,
) -> None:
    """Validate a single transaction CSV row."""
    for col in ["source_record_id", "account_provider_id", "transaction_type",
                "currency", "executed_at"]:
        if not row.get(col):
            result.error(row_index, col, f"Missing required column: {col}")

    txn_type = row.get("transaction_type", "")
    if txn_type and txn_type not in VALID_TRANSACTION_TYPES:
        result.error(row_index, "transaction_type", f"Invalid type: {txn_type!r}")

    currency = row.get("currency", "")
    if currency and not CURRENCY_RE.match(currency):
        result.error(row_index, "currency", f"Invalid currency: {currency!r}")

    # Decimal fields
    for col in ["quantity", "price", "amount", "fee"]:
        val = row.get(col)
        if val and val.strip():
            try:
                Decimal(val.strip())
            except Exception:
                result.error(row_index, col, f"Invalid decimal: {val!r}")

    # executed_at
    exec_str = row.get("executed_at")
    if exec_str:
        try:
            from apps.api.importers.csv_parser import parse_csv_datetime
            parse_csv_datetime(exec_str)
        except ValueError as exc:
            result.error(row_index, "executed_at", str(exc))

    # observed_at
    obs_str = row.get("observed_at")
    if obs_str:
        try:
            from apps.api.importers.csv_parser import parse_csv_datetime
            obs = parse_csv_datetime(obs_str)
            if obs and obs > datetime.now(timezone.utc):
                result.warning(row_index, "observed_at", "observed_at is in the future")
        except ValueError as exc:
            result.error(row_index, "observed_at", str(exc))

    isin = row.get("isin", "")
    if isin and len(isin) != 12:
        result.warning(row_index, "isin", f"ISIN should be 12 chars, got {len(isin)}")


def validate_cash_balance_row(
    row: dict[str, str], row_index: int, result: ValidationResult,
) -> None:
    """Validate a single cash balance CSV row."""
    for col in ["source_record_id", "account_provider_id", "currency", "amount",
                "observed_at"]:
        if not row.get(col):
            result.error(row_index, col, f"Missing required column: {col}")

    currency = row.get("currency", "")
    if currency and not CURRENCY_RE.match(currency):
        result.error(row_index, "currency", f"Invalid currency: {currency!r}")

    amt = row.get("amount")
    if amt and amt.strip():
        try:
            Decimal(amt.strip())
        except Exception:
            result.error(row_index, "amount", f"Invalid amount: {amt!r}")

    obs_str = row.get("observed_at")
    if obs_str:
        try:
            from apps.api.importers.csv_parser import parse_csv_datetime
            obs = parse_csv_datetime(obs_str)
            if obs and obs > datetime.now(timezone.utc):
                result.warning(row_index, "observed_at", "observed_at is in the future")
        except ValueError as exc:
            result.error(row_index, "observed_at", str(exc))


def validate_batch(
    rows: list[dict[str, str]],
    validator: callable,
) -> ValidationResult:
    """Run validator on every row, collecting all issues."""
    result = ValidationResult()
    seen_ids: set[str] = set()
    for i, row in enumerate(rows):
        validator(row, i, result)
        sid = row.get("source_record_id", "")
        if sid and sid in seen_ids:
            result.error(i, "source_record_id", f"Duplicate source_record_id in batch: {sid!r}")
        seen_ids.add(sid)
    return result
