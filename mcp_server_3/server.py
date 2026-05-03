"""
MCP Server 3 – Policy Resources
Transport: Streamable-HTTP (port 8003)
Exposes Mode of Payment, Return Policy, and Delivery Modes as MCP Resources
and as a searchable tool.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

POLICY_DOCS_DIR = os.getenv("POLICY_DOCS_DIR", "./mcp_server_3/policy_docs")

mcp = FastMCP(
    name="PolicyResourceServer",
    instructions=(
        "Provides access to ABC Consultants Ltd. commercial policy documents: "
        "Mode of Payment, Return & Refund Policy, and Delivery Modes & Logistics Partners. "
        "Use the 'get_policy' tool to retrieve specific policy content."
    ),
)

# ── Policy file mapping ───────────────────────────────────────────────────────

POLICY_MAP: dict[str, str] = {
    "payment": "payment_modes.md",
    "payment_modes": "payment_modes.md",
    "mode_of_payment": "payment_modes.md",
    "return": "return_policy.md",
    "return_policy": "return_policy.md",
    "refund": "return_policy.md",
    "delivery": "delivery_modes.md",
    "delivery_modes": "delivery_modes.md",
    "logistics": "delivery_modes.md",
    "shipping": "delivery_modes.md",
}

ALL_POLICIES = ["payment_modes", "return_policy", "delivery_modes"]


def _load_policy(filename: str) -> str:
    path = Path(POLICY_DOCS_DIR) / filename
    if not path.exists():
        return f"Policy document not found: {filename}"
    return path.read_text(encoding="utf-8")


# ── MCP Resources ─────────────────────────────────────────────────────────────

@mcp.resource("policy://payment-modes")
def payment_modes_resource() -> str:
    """Mode of Payment Policy for ABC Consultants Ltd."""
    return _load_policy("payment_modes.md")


@mcp.resource("policy://return-policy")
def return_policy_resource() -> str:
    """Return & Refund Policy for ABC Consultants Ltd."""
    return _load_policy("return_policy.md")


@mcp.resource("policy://delivery-modes")
def delivery_modes_resource() -> str:
    """Delivery Modes & Logistics Partners Policy for ABC Consultants Ltd."""
    return _load_policy("delivery_modes.md")


# ── Tool ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="get_policy",
    description=(
        "Retrieves the content of a specific commercial policy document. "
        "Available policies: 'payment' (Mode of Payment), 'return' (Return & Refund), "
        "'delivery' (Delivery Modes & Logistics). "
        "Pass 'all' to retrieve all three policies."
    ),
)
def get_policy(policy_name: str) -> str:
    """
    Args:
        policy_name: One of 'payment', 'return', 'delivery', or 'all'.

    Returns:
        Full Markdown text of the requested policy document(s).
    """
    key = policy_name.lower().strip().replace(" ", "_")

    if key == "all":
        parts = []
        for fname in ["payment_modes.md", "return_policy.md", "delivery_modes.md"]:
            parts.append(_load_policy(fname))
        return "\n\n" + "=" * 80 + "\n\n".join(parts)

    filename = POLICY_MAP.get(key)
    if not filename:
        available = ", ".join(sorted(set(POLICY_MAP.keys())))
        return (
            f"Unknown policy: '{policy_name}'. "
            f"Available options: {available}, or 'all'."
        )

    return _load_policy(filename)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_3_PORT", "8003"))
    print(f"🚀 MCP Server 3 (Policy Resources) → http://0.0.0.0:{port}/mcp")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
