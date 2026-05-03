"""
Remote Agent 1 – A2A Server
Hosts the LangGraph CRAG agent as a JSON-RPC 2.0 A2A endpoint.

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
    TaskMessage,
    TaskResult,
    TaskStatus,
    TextPart,
)
from remote_agent_1.graph import run_crag

load_dotenv()

# ── Agent Card definition ─────────────────────────────────────────────────────

AGENT_CARD = AgentCard(
    name="HR Policy RAG Specialist",
    description=(
        "A Corrective & Self-Reflective RAG agent specializing in ABC Consultants Ltd. "
        "HR policies. Answers questions about leave entitlements, higher education support, "
        "NPS retirement plans, working hours & WFH arrangements, and project party expense "
        "policies. Uses semantic retrieval from policy PDFs with web-search fallback."
    ),
    url=f"http://localhost:{os.getenv('REMOTE_AGENT_1_PORT', '8010')}",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="leave_policy_qa",
            name="Leave Policy Q&A",
            description="Answer questions about earned, casual, sick, maternity, paternity, "
                        "adoption, bereavement, sabbatical, LWP, and advance leave policies.",
            tags=["leave", "hr", "policy"],
            examples=[
                "How many earned leave days do JL5 employees get per year?",
                "What is the maximum carry-forward for privilege leave?",
                "How do I apply for maternity leave?",
            ],
        ),
        AgentSkill(
            id="education_policy_qa",
            name="Higher Education Policy Q&A",
            description="Answer questions about PhD/MBA support, sabbatical for education, "
                        "financial assistance, and service bond requirements.",
            tags=["education", "sabbatical", "hr"],
            examples=[
                "What financial support is available for a PhD program?",
                "How long is the sabbatical for non-PhD programs?",
            ],
        ),
        AgentSkill(
            id="nps_policy_qa",
            name="NPS Policy Q&A",
            description="Answer questions about NPS enrollment, contribution limits, "
                        "tax benefits, and withdrawal rules.",
            tags=["nps", "pension", "finance"],
            examples=[
                "What is the employer NPS contribution under the new tax regime?",
                "Can I make partial withdrawals from my NPS account?",
            ],
        ),
        AgentSkill(
            id="working_hours_qa",
            name="Working Hours & WFH Policy Q&A",
            description="Answer questions about standard working hours, WFH entitlement, "
                        "attendance, core hours, and flexible arrangements.",
            tags=["wfh", "working-hours", "attendance"],
            examples=[
                "How many WFH days am I allowed per month?",
                "What are the core working hours?",
            ],
        ),
        AgentSkill(
            id="project_party_qa",
            name="Project Party & Business Courtesy Q&A",
            description="Answer questions about project celebration expense limits, "
                        "gift policies, and approval requirements.",
            tags=["expenses", "project-party", "gifts"],
            examples=[
                "What is the per-person spend limit for a project party in India?",
                "What gifts are prohibited under the business courtesy policy?",
            ],
        ),
    ],
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
)

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="HR Policy RAG Agent (A2A)", version="1.0.0")


@app.get("/.well-known/agent.json", response_class=JSONResponse)
async def get_agent_card():
    return AGENT_CARD.model_dump()


@app.post("/")
async def handle_rpc(request: Request):
    body = await request.json()

    # JSON-RPC scaffolding
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

    # Extract question from message parts
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])
    question = ""
    for part in parts:
        if part.get("type") == "text":
            question = part.get("text", "")
            break

    if not question:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "No text found in message parts."},
                "id": rpc_id,
            }
        )

    # Run CRAG
    try:
        answer = await run_crag(question)
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
    port = int(os.getenv("REMOTE_AGENT_1_PORT", "8010"))
    print(f"🤖 Remote Agent 1 (HR Policy RAG) → http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
