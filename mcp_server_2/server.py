"""
MCP Server 2 – Product & Order Management
Transport: Streamable-HTTP (port 8002)
CSV-backed CRUD for products and orders.

Tools:
  1. get_products        – filter by brand, type, min_stock
  2. get_orders          – filter by product_type, min_quantity
  3. upsert_product      – insert or update product row
  4. upsert_order        – insert or update order row
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

PRODUCTS_CSV = os.getenv("PRODUCTS_CSV", "./data/products.csv")
ORDERS_CSV = os.getenv("ORDERS_CSV", "./data/orders.csv")

mcp = FastMCP(
    name="ProductOrderManager",
    instructions=(
        "Manages product inventory and order data for ABC Consultants Ltd.'s "
        "e-commerce platform. Use these tools to retrieve, insert, or update "
        "product and order records stored in CSV databases."
    ),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_csv(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path, dtype=str)


def _write_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)


def _df_to_json(df: pd.DataFrame) -> str:
    return df.to_json(orient="records", indent=2)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="get_products",
    description=(
        "Retrieves product records from the product database. "
        "Filters by brand_name, product_type, and/or minimum stock threshold."
    ),
)
def get_products(
    brand_name: Optional[str] = None,
    product_type: Optional[str] = None,
    min_stock: Optional[int] = None,
) -> str:
    """
    Args:
        brand_name: Filter by exact brand name (case-insensitive).
        product_type: One of Electronics | Home Appliances | Menswear |
                      Womenswear | Home Décor.
        min_stock: Return only products with quantity_in_stock >= min_stock.

    Returns:
        JSON array of matching product records.
    """
    df = _read_csv(PRODUCTS_CSV)

    if brand_name:
        df = df[df["brand_name"].str.lower() == brand_name.lower()]
    if product_type:
        df = df[df["product_type"].str.lower() == product_type.lower()]
    if min_stock is not None:
        df = df[df["quantity_in_stock"].astype(int) >= min_stock]

    if df.empty:
        return json.dumps({"message": "No products match the given filters.", "count": 0})

    return json.dumps({"count": len(df), "products": json.loads(_df_to_json(df))})


@mcp.tool(
    name="get_orders",
    description=(
        "Retrieves order records from the order database. "
        "Filters by product_type (via product join) and/or minimum order quantity."
    ),
)
def get_orders(
    product_type: Optional[str] = None,
    min_quantity: Optional[int] = None,
) -> str:
    """
    Args:
        product_type: Filter orders to this product type (joins products table).
        min_quantity: Return only orders with quantity >= min_quantity.

    Returns:
        JSON array of matching order records (enriched with product info).
    """
    orders = _read_csv(ORDERS_CSV)
    products = _read_csv(PRODUCTS_CSV)

    merged = orders.merge(products, on="product_code", how="left")

    if product_type:
        merged = merged[merged["product_type"].str.lower() == product_type.lower()]
    if min_quantity is not None:
        merged = merged[merged["quantity"].astype(int) >= min_quantity]

    if merged.empty:
        return json.dumps({"message": "No orders match the given filters.", "count": 0})

    cols = ["product_code", "client_code", "order_date", "quantity",
            "product_name", "product_type", "brand_name", "unit_price"]
    available = [c for c in cols if c in merged.columns]
    result = merged[available]

    return json.dumps({"count": len(result), "orders": json.loads(_df_to_json(result))})


@mcp.tool(
    name="upsert_product",
    description=(
        "Inserts a new product into the database or updates the record if the "
        "product_code already exists."
    ),
)
def upsert_product(
    product_code: str,
    product_name: str,
    product_type: str,
    brand_name: str,
    unit_price: float,
    quantity_in_stock: int,
) -> str:
    """
    Args:
        product_code: Unique product identifier (e.g. 'P1234').
        product_name: Descriptive name of the product.
        product_type: Category — Electronics | Home Appliances | Menswear |
                      Womenswear | Home Décor.
        brand_name: Manufacturer / brand.
        unit_price: Price per unit in INR.
        quantity_in_stock: Current stock count.

    Returns:
        Confirmation message with action taken (inserted | updated).
    """
    df = _read_csv(PRODUCTS_CSV)
    new_row = {
        "product_code": product_code,
        "product_name": product_name,
        "product_type": product_type,
        "brand_name": brand_name,
        "unit_price": str(unit_price),
        "quantity_in_stock": str(quantity_in_stock),
    }

    existing = df["product_code"] == product_code
    if existing.any():
        df.loc[existing, list(new_row.keys())] = list(new_row.values())
        action = "updated"
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        action = "inserted"

    _write_csv(df, PRODUCTS_CSV)
    return json.dumps({"action": action, "product_code": product_code, "record": new_row})


@mcp.tool(
    name="upsert_order",
    description=(
        "Inserts a new order into the database or updates the record if the "
        "combination of product_code + client_code + order_date already exists."
    ),
)
def upsert_order(
    product_code: str,
    client_code: str,
    order_date: str,
    quantity: int,
) -> str:
    """
    Args:
        product_code: Must match an existing product.
        client_code: Client identifier (e.g. 'C001').
        order_date: ISO date string YYYY-MM-DD.
        quantity: Number of units ordered.

    Returns:
        Confirmation message with action taken (inserted | updated).
    """
    df = _read_csv(ORDERS_CSV)
    new_row = {
        "product_code": product_code,
        "client_code": client_code,
        "order_date": order_date,
        "quantity": str(quantity),
    }

    mask = (
        (df["product_code"] == product_code)
        & (df["client_code"] == client_code)
        & (df["order_date"] == order_date)
    )

    if mask.any():
        df.loc[mask, "quantity"] = str(quantity)
        action = "updated"
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        action = "inserted"

    _write_csv(df, ORDERS_CSV)
    return json.dumps({"action": action, "record": new_row})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_2_PORT", "8002"))
    print(f"🚀 MCP Server 2 (Product & Order Manager) → http://0.0.0.0:{port}/mcp")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
