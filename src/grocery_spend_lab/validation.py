"""Validate normalized grocery receipt inputs without modifying them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import __version__

SCHEMA_VERSION = "1.0"
ORDER_FIELDS = {
    "receipt_key", "purchase_date", "purchase_type", "item_lines", "subtotal_cents",
    "savings_cents", "tax_cents", "fee_paid_cents", "other_fee_cents", "tip_cents", "total_cents",
}
ITEM_FIELDS = {
    "receipt_key", "purchase_date", "purchase_type", "description", "size", "upc", "is_weighted",
    "received", "paid_cents", "savings_cents", "unit_price_paid_cents", "original_unit_price_cents",
}


def _read_array(path: Path, label: str, errors: list[str]) -> pd.DataFrame:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        errors.append(f"{label} file does not exist: {path}")
        return pd.DataFrame()
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} file is not readable JSON: {exc}")
        return pd.DataFrame()
    if not isinstance(value, list):
        errors.append(f"{label} must be a JSON array")
        return pd.DataFrame()
    return pd.DataFrame(value)


def validate_inputs(orders_path: Path, items_path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    orders = _read_array(orders_path, "orders", errors)
    items = _read_array(items_path, "items", errors)

    missing_orders = sorted(ORDER_FIELDS - set(orders.columns))
    missing_items = sorted(ITEM_FIELDS - set(items.columns))
    if missing_orders:
        errors.append(f"orders is missing required fields: {', '.join(missing_orders)}")
    if missing_items:
        errors.append(f"items is missing required fields: {', '.join(missing_items)}")

    date_start = date_end = None
    if "purchase_date" in orders and len(orders):
        dates = pd.to_datetime(orders["purchase_date"], errors="coerce")
        invalid_dates = int(dates.isna().sum())
        if invalid_dates:
            errors.append(f"orders has {invalid_dates} invalid purchase_date value(s)")
        else:
            date_start = dates.min().date().isoformat()
            date_end = dates.max().date().isoformat()
    if "receipt_key" in orders:
        duplicate_orders = int(orders["receipt_key"].duplicated().sum())
        if duplicate_orders:
            errors.append(f"orders has {duplicate_orders} duplicate receipt_key value(s)")
    if "receipt_key" in orders and "receipt_key" in items:
        unknown = sorted(set(items["receipt_key"].dropna()) - set(orders["receipt_key"].dropna()))
        if unknown:
            errors.append(f"items references {len(unknown)} receipt_key value(s) absent from orders")
        empty_orders = set(orders["receipt_key"].dropna()) - set(items["receipt_key"].dropna())
        if empty_orders:
            warnings.append(f"{len(empty_orders)} order(s) have no item rows")
    if "description" in items and len(items):
        missing_descriptions = int(items["description"].isna().sum())
        if missing_descriptions:
            warnings.append(f"{missing_descriptions} item row(s) have no description and will remain Unknown")
    if "received" in items and "paid_cents" in items:
        excluded = int(((items["received"].fillna(0) <= 0) & (items["paid_cents"].fillna(0) <= 0)).sum())
        if excluded:
            warnings.append(f"{excluded} zero-received, zero-paid item row(s) will be excluded from incidence analysis")

    total_cents = None
    if "total_cents" in orders and len(orders):
        numeric_total = pd.to_numeric(orders["total_cents"], errors="coerce")
        if numeric_total.isna().any():
            errors.append("orders.total_cents contains nonnumeric values")
        else:
            total_cents = int(numeric_total.sum())

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "orders": {"path": str(orders_path), "rows": int(len(orders)), "date_start": date_start,
                   "date_end": date_end, "total_cents": total_cents},
        "items": {"path": str(items_path), "rows": int(len(items))},
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--items", required=True, type=Path)
    args = parser.parse_args(argv)
    report = validate_inputs(args.orders, args.items)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "command": "validate",
        "status": "completed_with_warnings" if report["valid"] and report["warnings"] else "completed" if report["valid"] else "failed",
        "data": {"orders": report["orders"], "items": report["items"]} if report["valid"] else None,
        "warnings": [{"code": "INPUT_WARNING", "message": message} for message in report["warnings"]],
        "artifacts": [],
        "error": None if report["valid"] else {"code": "INVALID_INPUT", "message": "Input validation failed.", "details": report["errors"]},
    }
    print(json.dumps(envelope, indent=2))
    return 0 if report["valid"] else 3
