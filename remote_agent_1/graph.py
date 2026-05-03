"""
Remote Agent 1 – Corrective & Self-Reflective RAG Graph (LangGraph)

Graph flow:
  route_question
    ├─→ retrieve  →  grade_documents
    │                   ├─→ generate  (relevant docs found)
    │                   └─→ web_search  (no relevant docs)
    │                           ├─→ generate  (retry>=1 or relevant web results)
    │                           └─→ transform_query  →  retrieve (loop)
    └─→ generate  (direct answer, no retrieval needed)
"""
from __future__ import annotations

import json
import os
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

load_dotenv()

MCP_SERVER_1_URL = os.getenv("MCP_SERVER_1_URL", "http://localhost:8001/mcp")
MAX_RETRIES = 2

# ── LLM ──────────────────────────────────────────────────────────────────────

_llm = None


def get_llm() -> ChatCohere:
    global _llm
    if _llm is None:
        _llm = ChatCohere(
            model="command-r-plus-08-2024",
            cohere_api_key=os.environ["COHERE_API_KEY"],
            temperature=0,
        )
    return _llm


# ── State ─────────────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    question: str          # current (possibly rewritten) question
    original_question: str # always the user's original input
    documents: list[dict]  # list of {"content": ..., "source": ...}
    generation: str        # final answer
    needs_web_search: bool # true if retrieval was unhelpful
    retries: int           # query-rewrite counter


# ── MCP helper ────────────────────────────────────────────────────────────────

async def _call_mcp_retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Call MCP Server 1's retrieve tool and return parsed chunks."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(MCP_SERVER_1_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "retrieve",
                    {"query": query, "top_k": top_k},
                )
                raw = result.content[0].text if result.content else ""
                chunks = raw.split("\n\n---\n\n")
                docs = []
                for chunk in chunks:
                    if chunk.strip():
                        # Extract source from header line if present
                        lines = chunk.strip().splitlines()
                        source = "policy_db"
                        if lines and lines[0].startswith("[Chunk"):
                            header = lines[0]
                            if "source=" in header:
                                source = header.split("source=")[1].split(" ")[0]
                            content = "\n".join(lines[1:]).strip()
                        else:
                            content = chunk.strip()
                        docs.append({"content": content, "source": source})
                return docs
    except Exception as exc:
        print(f"[MCP retrieve error] {exc}")
        return []


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def route_question(state: GraphState) -> GraphState:
    """Decide: needs retrieval from policy DB, or can answer directly."""
    question = state["question"]
    llm = get_llm()

    prompt = f"""You are a routing assistant for an HR policy QA system.

The knowledge base contains ABC Consultants Ltd. HR policy documents covering:
- Leave Policy (earned, casual, sick, maternity, paternity, bereavement, sabbatical, LWP)
- Higher Education Support Policy (PhD, MBA, financial assistance, sabbatical)
- National Pension System (NPS) Policy (contributions, tax benefits, withdrawals)
- Working Hours & WFH Policy (core hours, attendance, flexibility)
- Project Party & Business Courtesy Expense Policy (limits, approval, gifts)

Question: "{question}"

Respond ONLY with valid JSON, no other text:
- {{"action": "retrieve"}} if the question is about the above policies
- {{"action": "direct"}} if it is a general question you can answer without the policy DB"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result = json.loads(response.content.strip())
        action = result.get("action", "retrieve")
    except Exception:
        action = "retrieve"

    return {
        **state,
        "needs_web_search": action == "direct",
    }


async def retrieve(state: GraphState) -> GraphState:
    """Retrieve relevant chunks from MCP Server 1."""
    docs = await _call_mcp_retrieve(state["question"], top_k=5)
    return {**state, "documents": docs}


async def grade_documents(state: GraphState) -> GraphState:
    """Grade each retrieved document for relevance; set web-search flag if none relevant."""
    question = state["question"]
    documents = state["documents"]
    llm = get_llm()

    relevant: list[dict] = []
    for doc in documents:
        snippet = doc["content"][:600]
        prompt = f"""Is the following document excerpt relevant to answering the question?

Question: {question}
Document excerpt: {snippet}

Respond ONLY with JSON: {{"relevant": true}} or {{"relevant": false}}"""
        try:
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            parsed = json.loads(resp.content.strip())
            if parsed.get("relevant", True):
                relevant.append(doc)
        except Exception:
            relevant.append(doc)  # keep on parse error

    return {
        **state,
        "documents": relevant,
        "needs_web_search": len(relevant) == 0,
    }


async def generate(state: GraphState) -> GraphState:
    """Generate the final answer using available context (or pure LLM if no docs)."""
    question = state["original_question"]
    documents = state["documents"]
    llm = get_llm()

    if documents:
        context = "\n\n".join(
            f"[Source: {d['source']}]\n{d['content']}" for d in documents[:4]
        )
        prompt = f"""You are an expert HR policy assistant for ABC Consultants Ltd.
Use ONLY the context below to answer the question precisely.
Cite specific policy rules, job levels, and numbers where relevant.

Context:
{context}

Question: {question}

Answer:"""
    else:
        prompt = f"""You are an expert HR policy assistant for ABC Consultants Ltd.
Answer the following question to the best of your knowledge about standard corporate HR policies.
Be clear that this is a general answer if you lack specific policy details.

Question: {question}

Answer:"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {**state, "generation": response.content}


async def web_search(state: GraphState) -> GraphState:
    """Perform web search as fallback when retrieval yields no relevant docs."""
    question = state["question"]
    web_docs: list[dict] = []

    # Try Tavily first, fall back to DuckDuckGo
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        results = client.search(query=question, max_results=3)
        for r in results.get("results", []):
            web_docs.append({"content": r.get("content", ""), "source": r.get("url", "web")})
    except Exception:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for r in ddgs.text(question, max_results=3):
                    web_docs.append({"content": r.get("body", ""), "source": r.get("href", "web")})
        except Exception as exc:
            print(f"[Web search error] {exc}")

    return {**state, "documents": state["documents"] + web_docs}


async def transform_query(state: GraphState) -> GraphState:
    """Rewrite the query to improve retrieval recall."""
    llm = get_llm()
    prompt = f"""The following query did not return useful results from the HR policy knowledge base.
Rewrite it to be more specific and suitable for searching policy documents.

Original query: {state['question']}

Rewritten query (respond with ONLY the rewritten query, no preamble):"""

    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        new_question = resp.content.strip()
    except Exception:
        new_question = state["question"]

    return {
        **state,
        "question": new_question,
        "retries": state.get("retries", 0) + 1,
    }


# ── Edge conditions ───────────────────────────────────────────────────────────

def after_routing(state: GraphState) -> Literal["retrieve", "generate"]:
    return "generate" if state["needs_web_search"] else "retrieve"


def after_grading(state: GraphState) -> Literal["generate", "web_search"]:
    return "generate" if not state["needs_web_search"] else "web_search"


def after_web_search(state: GraphState) -> Literal["generate", "transform_query"]:
    retries = state.get("retries", 0)
    return "transform_query" if retries < MAX_RETRIES else "generate"


def after_transform(state: GraphState) -> Literal["retrieve"]:
    return "retrieve"


# ── Build graph ───────────────────────────────────────────────────────────────

def build_crag_graph():
    builder = StateGraph(GraphState)

    builder.add_node("route_question", route_question)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_documents", grade_documents)
    builder.add_node("generate", generate)
    builder.add_node("web_search", web_search)
    builder.add_node("transform_query", transform_query)

    builder.set_entry_point("route_question")

    builder.add_conditional_edges(
        "route_question",
        after_routing,
        {"retrieve": "retrieve", "generate": "generate"},
    )
    builder.add_edge("retrieve", "grade_documents")
    builder.add_conditional_edges(
        "grade_documents",
        after_grading,
        {"generate": "generate", "web_search": "web_search"},
    )
    builder.add_conditional_edges(
        "web_search",
        after_web_search,
        {"generate": "generate", "transform_query": "transform_query"},
    )
    builder.add_edge("transform_query", "retrieve")
    builder.add_edge("generate", END)

    return builder.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_crag_graph()
    return _graph


async def run_crag(question: str) -> str:
    """Public entry point: run the CRAG pipeline and return the answer."""
    initial_state: GraphState = {
        "question": question,
        "original_question": question,
        "documents": [],
        "generation": "",
        "needs_web_search": False,
        "retries": 0,
    }
    final_state = await get_graph().ainvoke(initial_state)
    return final_state["generation"]
