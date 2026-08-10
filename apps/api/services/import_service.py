"""Import service — orchestration layer for manual CSV import.

Sprint 009 Slice D — Manual Import + Data Source Foundation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.import_schemas import ImportResponse, ImportSummary
from apps.api.importers.asset_resolver import resolve_asset
from apps.api.importers.csv_parser import parse_csv_content
from apps.api.importers.validators import (
    validate_batch,
    validate_cash_balance_row,
    validate_position_row,
    validate_transaction_row,
)
from apps.api.models import (
    Account,
    CashBalance,
    DataSource,
    Position,
    Transaction,
)


def _parse_position_row(row: dict[str, str]) -> dict:
    """Parse position CSV row into DB-ready kwargs."""
    from apps.api.importers.csv_parser import parse_csv_datetime, parse_csv_decimal
    return {
        "source_record_id": row["source_record_id"].strip(),
        "quantity": Decimal(row["quantity"].strip()),
        "avg_cost": parse_csv_decimal(row.get("avg_cost")),
        "market_price": parse_csv_decimal(row.get("market_price")),
        "observed_at": parse_csv_datetime(row["observed_at"]),
    }


def _parse_transaction_row(row: dict[str, str]) -> dict:
    from apps.api.importers.csv_parser import parse_csv_datetime, parse_csv_decimal
    return {
        "source_record_id": row["source_record_id"].strip(),
        "transaction_type": row["transaction_type"].strip(),
        "quantity": parse_csv_decimal(row.get("quantity")),
        "price": parse_csv_decimal(row.get("price")),
        "amount": parse_csv_decimal(row.get("amount")),
        "fee": parse_csv_decimal(row.get("fee") or row.get("fees")),
        "executed_at": parse_csv_datetime(row["executed_at"]),
        "observed_at": parse_csv_datetime(row.get("observed_at") or row["executed_at"]),
    }


def _parse_balance_row(row: dict[str, str]) -> dict:
    from apps.api.importers.csv_parser import parse_csv_datetime
    return {
        "source_record_id": row["source_record_id"].strip(),
        "amount": Decimal(row["amount"].strip()),
        "observed_at": parse_csv_datetime(row["observed_at"]),
    }


def _resolve_account(
    session: Session, provider_account_id: str,
) -> Optional[Account]:
    return session.scalar(
        select(Account).where(Account.provider_account_id == provider_account_id)
    )


def _upsert_position(
    session: Session,
    account_id: UUID,
    asset_id: UUID,
    source: str,
    row_data: dict,
    currency: str,
) -> tuple[bool, bool]:
    """Upsert a position. Returns (was_created, was_updated)."""
    existing = session.scalar(
        select(Position).where(
            Position.source == source,
            Position.source_record_id == row_data["source_record_id"],
        ).with_for_update()
    )

    if existing is not None:
        existing.quantity = row_data["quantity"]
        if row_data.get("avg_cost") is not None:
            existing.avg_cost = row_data["avg_cost"]
        if row_data.get("market_price") is not None:
            existing.market_price = row_data["market_price"]
        existing.observed_at = row_data["observed_at"]
        existing.imported_at = datetime.now(timezone.utc)
        session.flush()
        return False, True

    position = Position(
        id=uuid4(),
        account_id=account_id,
        asset_id=asset_id,
        quantity=row_data["quantity"],
        quantity_source="provider_reported",
        avg_cost=row_data.get("avg_cost"),
        avg_cost_currency=currency,
        avg_cost_source=source if row_data.get("avg_cost") else None,
        market_price=row_data.get("market_price"),
        market_price_currency=currency,
        market_value=None,
        market_value_currency=None,
        cost_basis=None,
        cost_basis_currency=None,
        unrealized_gain_loss=None,
        observed_at=row_data["observed_at"],
        source=source,
        source_record_id=row_data["source_record_id"],
        is_latest=True,
    )
    session.add(position)
    session.flush()
    return True, False


def _upsert_cash_balance(
    session: Session,
    account_id: UUID,
    source: str,
    row_data: dict,
    currency: str,
) -> tuple[bool, bool]:
    existing = session.scalar(
        select(CashBalance).where(
            CashBalance.source == source,
            CashBalance.source_record_id == row_data["source_record_id"],
        ).with_for_update()
    )

    if existing is not None:
        existing.amount = row_data["amount"]
        existing.observed_at = row_data["observed_at"]
        session.flush()
        return False, True

    entry = CashBalance(
        id=uuid4(),
        account_id=account_id,
        currency=currency,
        amount=row_data["amount"],
        observed_at=row_data["observed_at"],
        source=source,
        source_record_id=row_data["source_record_id"],
        is_latest=True,
    )
    session.add(entry)
    session.flush()
    return True, False


def import_positions_from_csv(
    session: Session,
    csv_content: str,
    source_key: str,
) -> ImportResponse:
    """Import positions from CSV content. All-or-nothing transaction."""
    rows = parse_csv_content(csv_content)

    validation = validate_batch(rows, validate_position_row)
    if validation.has_errors:
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                warnings=len(validation.warnings),
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
            warnings=[{
                "code": "VALIDATION", "row_index": w.row_index,
                "column": w.column, "message": w.message,
            } for w in validation.warnings],
        )
    source_display = "csv"
    summary = ImportSummary(rows_processed=len(rows))
    assets_resolved: set[str] = set()
    assets_created_count = 0
    source_display = "csv"

    for i, row in enumerate(rows):
        try:
            parsed = _parse_position_row(row)
        except (ValueError, KeyError) as exc:
            validation.error(i, "", str(exc))
            continue

        account = _resolve_account(session, row["account_provider_id"].strip())
        if account is None:
            validation.error(
                i, "account_provider_id",
                f"Account not found: {row['account_provider_id']!r}",
            )
            continue

        currency = row.get("currency", account.currency or "USD").strip()
        symbol = row["symbol"].strip()
        exchange = row.get("exchange", "").strip() or None
        isin = row.get("isin", "").strip() or None
        name = row.get("name", "").strip() or None
        asset_type = row.get("asset_type", "").strip() or None

        # Asset resolution
        asset_before = resolve_asset(
            session, symbol, exchange, isin, currency, name, asset_type,
        )
        if asset_before.confidence == "unverified":
            assets_created_count += 1
        else:
            assets_resolved.add(str(asset_before.id))

        created, updated = _upsert_position(
            session, account.id, asset_before.id, source_display, parsed, currency,
        )
        if created:
            summary.positions_created += 1
        else:
            summary.positions_updated += 1

    # Re-check after row processing
    if validation.has_errors:
        session.rollback()
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                warnings=len(validation.warnings),
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
            warnings=[{
                "code": "VALIDATION", "row_index": w.row_index,
                "column": w.column, "message": w.message,
            } for w in validation.warnings],
        )

    summary.assets_resolved = len(assets_resolved)
    summary.assets_created = assets_created_count
    summary.warnings = len(validation.warnings)
    summary.errors = len(validation.errors)

    # Update data source last_import_at
    ds = session.scalar(
        select(DataSource).where(DataSource.source_key == source_key)
    )
    if ds is not None:
        ds.last_import_at = datetime.now(timezone.utc)

    return ImportResponse(
        source_key=source_key,
        imported_at=datetime.now(timezone.utc),
        summary=summary,
        warnings=[{
            "code": "VALIDATION", "row_index": w.row_index,
            "column": w.column, "message": w.message,
        } for w in validation.warnings],
    )


def import_transactions_from_csv(
    session: Session,
    csv_content: str,
    source_key: str,
) -> ImportResponse:
    """Import transactions from CSV. Duplicates are skipped silently."""
    rows = parse_csv_content(csv_content)
    validation = validate_batch(rows, validate_transaction_row)

    if validation.has_errors:
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                warnings=len(validation.warnings),
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
            warnings=[{
                "code": "VALIDATION", "row_index": w.row_index,
                "column": w.column, "message": w.message,
            } for w in validation.warnings],
        )

    summary = ImportSummary(rows_processed=len(rows))
    source_display = "csv"

    for i, row in enumerate(rows):
        sid = row["source_record_id"].strip()

        # Check duplicate
        existing = session.scalar(
            select(Transaction).where(
                Transaction.source == source_display,
                Transaction.source_record_id == sid,
            )
        )
        if existing is not None:
            summary.transactions_skipped += 1
            continue

        account = _resolve_account(session, row["account_provider_id"].strip())
        if account is None:
            validation.error(
                i, "account_provider_id",
                f"Account not found: {row['account_provider_id']!r}",
            )
            continue

        try:
            parsed = _parse_transaction_row(row)
        except (ValueError, KeyError) as exc:
            validation.error(i, "", str(exc))
            continue

        currency = row.get("currency", account.currency or "USD").strip()

        # Resolve asset if symbol provided
        asset_id: Optional[UUID] = None
        symbol = (row.get("symbol") or "").strip()
        if symbol:
            exchange = row.get("exchange", "").strip() or None
            isin = row.get("isin", "").strip() or None
            name = row.get("name", "").strip() or None
            asset_type = row.get("asset_type", "").strip() or None
            asset = resolve_asset(
                session, symbol, exchange, isin, currency, name, asset_type,
            )
            asset_id = asset.id

        txn = Transaction(
            id=uuid4(),
            account_id=account.id,
            asset_id=asset_id,
            transaction_type=parsed["transaction_type"],
            quantity=parsed["quantity"],
            price=parsed.get("price"),
            price_currency=currency if parsed.get("price") else None,
            amount=parsed.get("amount"),
            amount_currency=currency,
            fee=parsed.get("fee"),
            fee_currency=currency if parsed.get("fee") else None,
            executed_at=parsed["executed_at"],
            source=source_display,
            source_record_id=sid,
        )
        session.add(txn)
        summary.transactions_created += 1

    if validation.has_errors:
        session.rollback()
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                transactions_skipped=summary.transactions_skipped,
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
        )

    summary.warnings = len(validation.warnings)
    summary.errors = len(validation.errors)

    ds = session.scalar(
        select(DataSource).where(DataSource.source_key == source_key)
    )
    if ds is not None:
        ds.last_import_at = datetime.now(timezone.utc)

    return ImportResponse(
        source_key=source_key,
        imported_at=datetime.now(timezone.utc),
        summary=summary,
        warnings=[{
            "code": "VALIDATION", "row_index": w.row_index,
            "column": w.column, "message": w.message,
        } for w in validation.warnings],
    )


def import_cash_balances_from_csv(
    session: Session,
    csv_content: str,
    source_key: str,
) -> ImportResponse:
    """Import cash balances from CSV."""
    rows = parse_csv_content(csv_content)
    validation = validate_batch(rows, validate_cash_balance_row)

    if validation.has_errors:
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                warnings=len(validation.warnings),
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
        )

    summary = ImportSummary(rows_processed=len(rows))
    source_display = "csv"

    for i, row in enumerate(rows):
        account = _resolve_account(session, row["account_provider_id"].strip())
        if account is None:
            validation.error(
                i, "account_provider_id",
                f"Account not found: {row['account_provider_id']!r}",
            )
            continue

        try:
            parsed = _parse_balance_row(row)
        except (ValueError, KeyError) as exc:
            validation.error(i, "", str(exc))
            continue

        currency = row.get("currency", account.currency or "USD").strip()
        created, updated = _upsert_cash_balance(
            session, account.id, source_display, parsed, currency,
        )
        if created:
            summary.cash_balances_created += 1
        else:
            summary.cash_balances_updated += 1

    if validation.has_errors:
        session.rollback()
        return ImportResponse(
            source_key=source_key,
            imported_at=datetime.now(timezone.utc),
            summary=ImportSummary(
                rows_processed=len(rows),
                errors=len(validation.errors),
                warnings=len(validation.warnings),
            ),
            errors=[{
                "row_index": e.row_index, "column": e.column, "message": e.message,
            } for e in validation.errors],
        )

    summary.warnings = len(validation.warnings)
    summary.errors = len(validation.errors)

    ds = session.scalar(
        select(DataSource).where(DataSource.source_key == source_key)
    )
    if ds is not None:
        ds.last_import_at = datetime.now(timezone.utc)

    return ImportResponse(
        source_key=source_key,
        imported_at=datetime.now(timezone.utc),
        summary=summary,
        warnings=[{
            "code": "VALIDATION", "row_index": w.row_index,
            "column": w.column, "message": w.message,
        } for w in validation.warnings],
    )
