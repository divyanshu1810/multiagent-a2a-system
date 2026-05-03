"""
Host Agent – Google ADK Router
Routes user queries to Remote Agent 1 (HR policies) or Remote Agent 2 (products/orders/policy).
"""
from __future__ import annotations

import json
import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

REMOTE_AGENT_1_URL = os.getenv("REMOTE_AGENT_1_URL", "http://localhost:8010")
REMOTE_AGENT_2_URL = os.getenv("REMOTE_AGENT_2_URL", "http://localhost:8011")

RouteTarget = Literal["hr_policy_agent", "product_order_agent"]


# ── Routing logic (ADK-compatible function tool) ──────────────────────────────

async def classify_and_route(query: str) -> dict:
    """
    Classify the user query and route it to the appropriate remote agent.
    Returns {"agent": "hr_policy_agent" | "product_order_agent", "response": "..."}
    """
    from langchain_cohere import ChatCohere
    from langchain_core.messages import HumanMessage

    llm = ChatCohere(
        model="command-r-plus-08-2024",
        cohere_api_key=os.environ["COHERE_API_KEY"],
        temperature=0,
    )

    routing_prompt = f"""You are a query router for ABC Consultants Ltd.'s AI assistant.

Route queries to:
- "hr_policy_agent": For questions about ABC Consultants' internal HR policies:
  leave entitlements, maternity/paternity leave, sick leave, WFH policy, working hours,
  sabbatical, NPS/pension, higher education support, project party expense limits.

- "product_order_agent": For everything related to products, orders, inventory,
  and commercial policies (payment methods, return/refund, delivery/shipping).

Query: "{query}"

Respond ONLY with JSON: {{"route": "hr_policy_agent"}} or {{"route": "product_order_agent"}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=routing_prompt)])
        result = json.loads(response.content.strip())
        route = result.get("route", "hr_policy_agent")
        if route not in ("hr_policy_agent", "product_order_agent"):
            route = "hr_policy_agent"
    except Exception:
        route = "hr_policy_agent"

    return {"route": route}


async def call_remote_agent(query: str, route: str) -> str:
    """Send task to the chosen remote agent via A2A and return the text response."""
    from host_agent.a2a_client import A2AClient

    url = REMOTE_AGENT_1_URL if route == "hr_policy_agent" else REMOTE_AGENT_2_URL
    client = A2AClient(agent_url=url)

    try:
        result = await client.send_task(query)
        return result.text()
    except Exception as exc:
        return f"[Agent error] {exc}"


async def run_host_agent(query: str) -> dict:
    """
    Full host-agent pipeline:
      1. Route query
      2. Call remote agent
      3. Return enriched response with metadata
    """
    routing = await classify_and_route(query)
    route = routing["route"]

    agent_label = (
        "HR Policy RAG Specialist" if route == "hr_policy_agent"
        else "Product & Order Workflow Agent"
    )

    response_text = await call_remote_agent(query, route)

    return {
        "query": query,
        "routed_to": agent_label,
        "route_key": route,
        "response": response_text,
    }


# ── Google ADK Agent definition ───────────────────────────────────────────────

def build_adk_agent():
    """Build and return a Google ADK LlmAgent wrapping the host router."""
    try:
        from google.adk.agents import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.tools import FunctionTool

        async def route_and_answer(query: str) -> str:
            """Route the query to the appropriate specialized agent and return its answer."""
            result = await run_host_agent(query)
            return f"[Routed to: {result['routed_to']}]\n\n{result['response']}"

        model = LiteLlm(
            model="cohere/command-r-plus-08-2024",
            api_key=os.environ["COHERE_API_KEY"],
        )

        agent = LlmAgent(
            name="HostRouterAgent",
            model=model,
            description=(
                "Master routing agent for ABC Consultants Ltd. "
                "Directs HR policy questions to the RAG specialist and "
                "product/order/commercial-policy questions to the workflow agent."
            ),
            instruction=(
                "You are a helpful assistant for ABC Consultants Ltd. "
                "Use the route_and_answer tool to answer every user question. "
                "Present the answer clearly, preserving all details from the specialized agent."
            ),
            tools=[FunctionTool(func=route_and_answer)],
        )
        return agent

    except ImportError:
        # ADK not installed — return None; Gradio app will use run_host_agent directly
        return None
