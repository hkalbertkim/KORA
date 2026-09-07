"""Bounded order-cleaning reference workload; no model or external effects."""

import re
import unicodedata


def clean_orders(rows):
    """First valid order ID wins; invalid rows never reserve an ID."""
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("rows must be a list of at most 10000")
    orders, seen, rejected, duplicates = [], set(), [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "id",
            "sku",
            "quantity",
            "unit_price",
        }:
            rejected.append({"index": index, "reason": "invalid-fields"})
            continue
        if not all(isinstance(row[k], str) for k in ("id", "sku")):
            rejected.append({"index": index, "reason": "invalid-text"})
            continue
        key = unicodedata.normalize("NFKC", row["id"]).strip().upper()
        sku = unicodedata.normalize("NFKC", row["sku"]).strip().upper()
        if not all(re.fullmatch(r"[A-Z0-9-]{1,32}", x) for x in (key, sku)):
            rejected.append({"index": index, "reason": "invalid-format"})
            continue
        if (
            any(
                type(row[k]) is not int or not 0 <= row[k] <= 10**9
                for k in ("quantity", "unit_price")
            )
            or row["quantity"] == 0
        ):
            rejected.append({"index": index, "reason": "invalid-number"})
            continue
        if key in seen:
            duplicates.append(index)
            continue
        seen.add(key)
        orders.append(
            {
                "id": key,
                "sku": sku,
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "total": row["quantity"] * row["unit_price"],
            }
        )
    return {
        "orders": orders,
        "rejected": rejected,
        "duplicates": duplicates,
        "total": sum(row["total"] for row in orders),
    }
