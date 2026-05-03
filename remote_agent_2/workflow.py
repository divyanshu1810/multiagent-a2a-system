"""
Remote Agent 2 – Agno Workflow
3-step pipeline:
  Step 1: Classify query → 'insert' | 'retrieve' | 'policy'
  Step 2A: If insert/retrieve → Agent with MCP Server 2 tools
  Step 2B: If policy         → Agent with MCP Server 3 tool
  Step 3: Return final response
"""
from __future__ import annotations

import json
import os
from typing import Iterator, Literal

from dotenv import load_dotenv

load_dotenv()

MCP_SERVER_2_URL = os.getenv("MCP_SERVER_2_URL", "http://localhost:8002/mcp")
MCP_SERVER_3_URL = os.getenv("MCP_SERVER_3_URL", "http://localhost:8003/mcp")

QueryClass = Literal["insert", "retrieve", "policy"]


# ── Step 1: Classification ────────────────────────────────────────────────────

async def classify_query(query: str) -> QueryClass:
    """Use Cohere structured output to classify the query."""
    from langchain_cohere import ChatCohere
    from langchain_core.messages import HumanMessage

    llm = ChatCohere(
        model="command-r-plus-08-2024",
        cohere_api_key=os.environ["COHERE_API_KEY"],
        temperature=0,
    )

    prompt = f"""Classify the following user query into EXACTLY ONE of these categories:

- "insert"   → User wants to add, create, or update a product or order record
- "retrieve" → User wants to search, list, or get information about products or orders
- "policy"   → User is asking about payment modes, return/refund policy, or delivery/shipping information

Query: "{query}"

Respond with ONLY valid JSON: {{"classification": "insert"}} or {{"classification": "retrieve"}} or {{"classification": "policy"}}
No other text."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result = json.loads(response.content.strip())
        cls = result.get("classification", "retrieve")
        if cls not in ("insert", "retrieve", "policy"):
            cls = "retrieve"
        return cls  # type: ignore[return-value]
    except Exception:
        return "retrieve"


# ── Step 2A: Product/Order Agent ──────────────────────────────────────────────

async def run_product_order_agent(query: str) -> str:
    """Agent with access to MCP Server 2 tools (product/order CRUD)."""
    try:
        from agno.agent import Agent
        from agno.models.cohere import Cohere as AgnoCohere
        from agno.tools.mcp import MCPTools

        async with MCPTools(
            url=MCP_SERVER_2_URL,
            transport="streamable-http",
        ) as mcp_tools:
            agent = Agent(
                name="ProductOrderAgent",
                model=AgnoCohere(
                    id="command-r-plus-08-2024",
                    api_key=os.environ["COHERE_API_KEY"],
                ),
                tools=[mcp_tools],
                instructions=(
                    "You manage product and order data for ABC Consultants Ltd. "
                    "Use the available tools to retrieve or insert records as requested. "
                    "Always confirm the action taken and summarise the results clearly."
                ),
                show_tool_calls=True,
                markdown=True,
            )
            response = await agent.arun(query)
            return response.content if hasattr(response, "content") else str(response)

    except ImportError:
        # Fallback: call MCP tools directly via httpx
        return await _fallback_product_order(query)


async def _fallback_product_order(query: str) -> str:
    """Direct MCP call fallback if Agno is unavailable."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from langchain_cohere import ChatCohere
    from langchain_core.messages import HumanMessage

    llm = ChatCohere(
        model="command-r-plus-08-2024",
        cohere_api_key=os.environ["COHERE_API_KEY"],
    )

    # Get available tools
    async with streamablehttp_client(MCP_SERVER_2_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]

            # Ask LLM which tool to use
            tool_prompt = f"""Available tools: {tool_names}
Query: {query}
Which tool should I call and with what arguments?
Respond with JSON: {{"tool": "<name>", "args": {{...}}}}"""
            resp = await llm.ainvoke([HumanMessage(content=tool_prompt)])
            try:
                call = json.loads(resp.content.strip())
                result = await session.call_tool(call["tool"], call["args"])
                return result.content[0].text if result.content else "Done."
            except Exception as e:
                return f"Could not process request: {e}"


# ── Step 2B: Policy Agent ─────────────────────────────────────────────────────

async def run_policy_agent(query: str) -> str:
    """Agent with access to MCP Server 3 (policy resources)."""
    try:
        from agno.agent import Agent
        from agno.models.cohere import Cohere as AgnoCohere
        from agno.tools.mcp import MCPTools

        async with MCPTools(
            url=MCP_SERVER_3_URL,
            transport="streamable-http",
        ) as mcp_tools:
            agent = Agent(
                name="PolicyAgent",
                model=AgnoCohere(
                    id="command-r-plus-08-2024",
                    api_key=os.environ["COHERE_API_KEY"],
                ),
                tools=[mcp_tools],
                instructions=(
                    "You answer questions about ABC Consultants Ltd. commercial policies: "
                    "Mode of Payment, Return & Refund Policy, and Delivery Modes. "
                    "Use the get_policy tool to retrieve relevant policy details."
                ),
                show_tool_calls=True,
                markdown=True,
            )
            response = await agent.arun(query)
            return response.content if hasattr(response, "content") else str(response)

    except ImportError:
        return await _fallback_policy(query)


async def _fallback_policy(query: str) -> str:
    """Direct MCP call fallback if Agno is unavailable."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from langchain_cohere import ChatCohere
    from langchain_core.messages import HumanMessage, SystemMessage

    # Determine which policy to fetch
    q_lower = query.lower()
    if "payment" in q_lower or "pay" in q_lower:
        policy_key = "payment"
    elif "return" in q_lower or "refund" in q_lower:
        policy_key = "return"
    elif "delivery" in q_lower or "shipping" in q_lower or "logistics" in q_lower:
        policy_key = "delivery"
    else:
        policy_key = "all"

    async with streamablehttp_client(MCP_SERVER_3_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_policy", {"policy_name": policy_key})
            policy_text = result.content[0].text if result.content else ""

    llm = ChatCohere(
        model="command-r-plus-08-2024",
        cohere_api_key=os.environ["COHERE_API_KEY"],
    )
    resp = await llm.ainvoke([
        SystemMessage(content=f"Use this policy document to answer:\n\n{policy_text[:4000]}"),
        HumanMessage(content=query),
    ])
    return resp.content


# ── Main Workflow ─────────────────────────────────────────────────────────────

async def run_workflow(query: str) -> str:
    """
    Full 3-step Agno-style workflow:
      1. Classify
      2. Route to correct agent
      3. Return response
    """
    # Step 1: Classify
    classification = await classify_query(query)
    print(f"[Workflow] Classification: {classification}")

    # Step 2: Route
    if classification in ("insert", "retrieve"):
        raw_response = await run_product_order_agent(query)
    else:  # policy
        raw_response = await run_policy_agent(query)

    # Step 3: Final response (pass through – agents already produce polished output)
    return raw_response
