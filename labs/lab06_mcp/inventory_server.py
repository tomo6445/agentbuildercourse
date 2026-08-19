"""
Lab 6a — wrap a deliberately awful legacy inventory API.

The legacy API: inconsistent casing, an endpoint that returns HTTP 200 with an
error body, pagination that changes shape past page 10. Your server's job is to
hide all of that behind an interface designed to the M2 rubric.

MCP does not exempt you from tool design. This server is graded on the same
rubric as Lab 2.
"""

from __future__ import annotations

from .protocol import Server

# ---- the legacy API, in all its glory -------------------------------------

_STOCK = {
    "AC-1180": {"Warehouse_A": 42, "warehouse_b": 0, "WAREHOUSE-C": 7},
    "BX-2240": {"Warehouse_A": 0, "warehouse_b": 15, "WAREHOUSE-C": 0},
}


def legacy_get_stock(sku):
    """Returns 200 with an error body for an unknown SKU, because of course."""
    if sku.upper() not in _STOCK:
        return {"status": "ok", "data": None, "err": "SKU_NOT_FOUND", "code": 0}
    return {"status": "ok", "data": _STOCK[sku.upper()], "err": None, "code": 0}


def legacy_list(page=1):
    skus = sorted(_STOCK)
    if page > 10:                      # shape changes past page 10
        return {"items": skus, "next": None}
    return {"data": {"rows": skus, "paging": {"page": page, "more": False}}}


# ---- the server ------------------------------------------------------------

server = Server("inventory")


@server.tool(
    name="inventory_check_stock",
    description=(
        "Check available stock for a SKU across all warehouses. "
        "Use this whenever the user asks whether something is in stock, how many "
        "are available, or where an item is held. "
        "Returns per-warehouse counts plus a total and the timestamp the figures "
        "were refreshed. Warehouse names are normalised to warehouse_a, "
        "warehouse_b, warehouse_c. "
        "An unknown SKU returns a clear 'no such SKU' message, not an error — "
        "check the SKU with the user rather than retrying."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "sku": {"type": "string",
                    "description": "The stock keeping unit, e.g. 'AC-1180'. "
                                   "Case-insensitive."},
            "warehouse": {"type": "string",
                          "enum": ["warehouse_a", "warehouse_b", "warehouse_c", "any"],
                          "description": "Limit to one warehouse, or 'any' for all."},
        },
        "required": ["sku"],
    },
)
def check_stock(sku: str, warehouse: str = "any") -> str:
    raw = legacy_get_stock(sku)
    # The legacy API says 200/ok and hides the failure in `err`. Unwrap it here,
    # once, rather than letting every caller learn this the hard way.
    if raw.get("err") == "SKU_NOT_FOUND" or raw.get("data") is None:
        return (f"No such SKU {sku!r}. Check the code with the user — SKUs look "
                f"like 'AC-1180'.")

    normalised = {k.lower().replace("-", "_"): v for k, v in raw["data"].items()}
    if warehouse != "any":
        count = normalised.get(warehouse, 0)
        return f"{sku.upper()} in {warehouse}: {count} units"
    total = sum(normalised.values())
    detail = ", ".join(f"{k}: {v}" for k, v in sorted(normalised.items()))
    return f"{sku.upper()} total {total} units ({detail}); refreshed 2026-08-19T09:00Z"


@server.resource(
    uri="inventory://schema",
    name="Inventory schema",
    description="Field definitions and warehouse codes, for the host to include "
                "when the user is asking about data shape rather than stock.",
)
def schema() -> str:
    return ("sku: string, uppercase, format XX-0000\n"
            "warehouses: warehouse_a, warehouse_b, warehouse_c\n"
            "counts: integer, units on hand, excludes reserved stock")


@server.prompt(
    name="stock_report",
    description="Produce the weekly stock report for a list of SKUs.",
)
def stock_report(skus: str = "") -> list:
    return [{"role": "user",
             "content": f"Produce the weekly stock report for: {skus}. "
                        f"Flag anything below 10 units."}]
