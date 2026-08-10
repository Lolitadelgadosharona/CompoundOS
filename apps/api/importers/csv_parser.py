"""CSV parser for manual financial data import.

Sprint 009 Slice D — Manual Import + Data Source Foundation.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Optional


class ParseError(Exception):
    """A single row failed to parse."""

    def __init__(self, line_number: int, message: str):
        self.line_number = line_number
        self.message = message
        super().__init__(f"Line {line_number}: {message}")


class BatchParseError(Exception):
    """One or more rows failed to parse."""

    def __init__(self, errors: list[ParseError]):
        self.errors = errors
        super().__init__(f"{len(errors)} parse error(s)")


def parse_csv_content(content: str) -> list[dict[str, str]]:
    """Parse CSV string into list of row dicts. Raises BatchParseError on failure."""
    errors: list[ParseError] = []
    rows: list[dict[str, str]] = []

    try:
        reader = csv.DictReader(StringIO(content))
    except Exception as exc:
        raise ParseError(0, f"Cannot read CSV: {exc}") from exc

    if reader.fieldnames is None:
        raise ParseError(0, "CSV has no header row")

    for line_num, row in enumerate(reader, start=2):  # header is line 1
        stripped = {k.strip(): (v or "").strip() for k, v in row.items() if v or k.strip()}
        if not stripped:
            continue  # skip blank rows
        rows.append(stripped)

    if errors:
        raise BatchParseError(errors)

    if not rows:
        raise ParseError(0, "CSV contains no data rows")

    return rows


def parse_decimal(value: str | None) -> Optional[Decimal]:
    """Parse a string as Decimal, returning None for empty/None."""
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal: {value!r}") from exc


def parse_iso8601(value: str | None) -> datetime:
    """Parse ISO 8601 timestamp string."""
    if value is None or value.strip() == "":
        raise ValueError("Missing required timestamp")
    raw = value.strip()
    # Try ISO 8601 with Z suffix
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO 8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_csv_decimal(value: str | None) -> Optional[Decimal]:
    """Parse a Decimal, returning None for empty."""
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        raise ValueError(f"Invalid decimal value: {value!r}")


def parse_csv_int(value: str | None) -> Optional[int]:
    """Parse int, returning None for empty."""
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        raise ValueError(f"Invalid integer: {value!r}")


def parse_csv_datetime(value: str | None) -> Optional[datetime]:
    """Parse ISO 8601 datetime, returning None for empty."""
    if not value or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"Invalid ISO 8601 datetime: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
VALID_ASSET_TYPES = frozenset({
    "ETF", "STOCK", "BOND", "CASH", "MONEY_MARKET", "FUND", "OTHER",
})
VALID_TRANSACTION_TYPES = frozenset({
    "BUY", "SELL", "DIVIDEND", "INTEREST", "DEPOSIT",
    "WITHDRAWAL", "FEE", "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "OTHER",
})
