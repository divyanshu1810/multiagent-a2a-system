"""
MCP Server 1 – HR Policy Retriever
Transport: Streamable-HTTP (port 8001)
Tools:
  • retrieve(query, top_k, tag, allowed_sources) → semantically-ranked chunks
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(
    name="HRPolicyRetriever",
    instructions=(
        "Retrieves relevant chunks from ABC Consultants Ltd. HR policy documents. "
        "Supports semantic search with optional tag and source filtering."
    ),
)

# Lazy-loaded vector store
_vectorstore = None


def _get_store():
    global _vectorstore
    if _vectorstore is None:
        from mcp_server_1.vector_store import get_or_build_vector_store
        _vectorstore = get_or_build_vector_store()
    return _vectorstore


# ── Tool ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="retrieve",
    description=(
        "Semantically search ABC Consultants Ltd. HR policy documents and return "
        "the most relevant text chunks. Supports filtering by document tag "
        "(e.g. 'leave_policy', 'nps_policy') and by allowed_sources (PDF filenames)."
    ),
)
def retrieve(
    query: str,
    top_k: int = 5,
    tag: Optional[str] = None,
    allowed_sources: Optional[list[str]] = None,
) -> str:
    """
    Args:
        query: The natural-language search query.
        top_k: Number of chunks to return (default 5).
        tag: Filter by document tag. Values: leave_policy | education_policy |
             nps_policy | working_hours | project_party | general_policy
        allowed_sources: List of PDF filenames to restrict search to.

    Returns:
        Formatted string of ranked document chunks with metadata.
    """
    store = _get_store()

    # Build Chroma filter
    where: dict = {}
    if tag and allowed_sources:
        where = {"$and": [{"tag": tag}, {"source": {"$in": allowed_sources}}]}
    elif tag:
        where = {"tag": tag}
    elif allowed_sources:
        where = {"source": {"$in": allowed_sources}}

    try:
        results = store.similarity_search_with_relevance_scores(
            query,
            k=top_k,
            filter=where if where else None,
        )
    except Exception as exc:
        return f"Retrieval error: {exc}"

    if not results:
        return "No relevant documents found for the given query and filters."

    parts: list[str] = []
    for i, (doc, score) in enumerate(results, 1):
        parts.append(
            f"[Chunk {i} | source={doc.metadata.get('source', 'unknown')} "
            f"| tag={doc.metadata.get('tag', 'unknown')} | score={score:.3f}]\n"
            f"{doc.page_content.strip()}"
        )

    return "\n\n---\n\n".join(parts)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_1_PORT", "8001"))
    print(f"🚀 MCP Server 1 (HR Policy Retriever) → http://0.0.0.0:{port}/mcp")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
