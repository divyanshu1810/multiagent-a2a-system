"""
Remote Agent 2 – A2A Server
Hosts the Agno Workflow agent as a JSON-RPC 2.0 A2A endpoint.

Endpoints:
  GET  /.well-known/agent.json   →  Agent Card
  POST /                          →  JSON-RPC task handler
"""
from __future__ import annotations

import os
import uuid

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from common.a2a_types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    TaskArtifact,
    TaskResult,
    TaskStatus,
    TextPart,
)
from remote_agent_2.workflow import run_workflow

load_dotenv()

# ── Agent Card ────────────────────────────────────────────────────────────────

AGENT_CARD = AgentCard(
    name="Product & Order Workflow Agent",
    description=(
        "An Agno-powered workflow agent that classifies queries as 'insert', 'retrieve', "
        "or 'policy' and routes them to the appropriate specialist agent. Handles all "
        "product and order management tasks (CSV-backed) and commercial policy queries "
        "(payment, return, delivery). "
    ),
    url=f"http://localhost:{os.getenv('REMOTE_AGENT_2_PORT', '8011')}",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="product_retrieval",
            name="Product Retrieval",
            description="Search and filter product inventory by brand, type, and stock level.",
            tags=["products", "inventory", "retrieve"],
            examples=[
                "Show me all Samsung electronics with stock > 20",
                "List all Womenswear products from Biba",
            ],
        ),
        AgentSkill(
            id="order_retrieval",
            name="Order Retrieval",
            description="Search and filter order records by product type and quantity.",
            tags=["orders", "retrieve"],
            examples=[
                "Show all orders with quantity greater than 10",
                "List all Electronics orders",
            ],
        ),
        AgentSkill(
            id="product_insert",
            name="Product Insert / Update",
            description="Add a new product or update an existing product record.",
            tags=["products", "insert", "update"],
            examples=[
                "Add a new Sony TV with product code P1200, price ₹45000, stock 30",
            ],
        ),
        AgentSkill(
            id="order_insert",
            name="Order Insert / Update",
            description="Record a new order or update an existing order.",
            tags=["orders", "insert", "update"],
            examples=[
                "Create an order for product P1001, client C005, date 2025-06-01, quantity 5",
            ],
        ),
        AgentSkill(
            id="policy_lookup",
            name="Commercial Policy Lookup",
            description="Answer queries about payment modes, return/refund policy, "
                        "and delivery modes & logistics partners.",
            tags=["policy", "payment", "return", "delivery"],
            examples=[
                "What is the COD limit?",
                "How long does a return take for electronics?",
                "Which courier partners do you use for same-day delivery?",
            ],
        ),
    ],
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
)

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Product & Order Workflow Agent (A2A)", version="1.0.0")


@app.get("/.well-known/agent.json", response_class=JSONResponse)
async def get_agent_card():
    return AGENT_CARD.model_dump()


@app.post("/")
async def handle_rpc(request: Request):
    body = await request.json()

    rpc_id = body.get("id", str(uuid.uuid4()))
    method = body.get("method", "")
    params = body.get("params", {})

    if method not in ("tasks/send", "message/send"):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": rpc_id,
            }
        )

    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])
    query = ""
    for part in parts:
        if part.get("type") == "text":
            query = part.get("text", "")
            break

    if not query:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "No text in message parts."},
                "id": rpc_id,
            }
        )

    try:
        answer = await run_workflow(query)
        result = TaskResult(
            id=task_id,
            status=TaskStatus(state="completed"),
            artifacts=[TaskArtifact(name="answer", parts=[TextPart(text=answer)])],
        )
        return JSONResponse(
            {"jsonrpc": "2.0", "result": result.model_dump(), "id": rpc_id}
        )
    except Exception as exc:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(exc)},
                "id": rpc_id,
            }
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("REMOTE_AGENT_2_PORT", "8011"))
    print(f"🤖 Remote Agent 2 (Product & Order Workflow) → http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
