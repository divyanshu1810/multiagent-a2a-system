"""
MCP Server 1 – Vector Store builder and loader.
Uses PyPDF + RecursiveCharacterTextSplitter + CohereEmbeddings + Chroma.

Run once to build:
    python -m mcp_server_1.vector_store
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_cohere import CohereEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

POLICIES_DIR = os.getenv("POLICIES_DIR", "./policies")
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
COLLECTION_NAME = "abc_hr_policies"

# Tag mapping: filename fragment → tag
FILE_TAGS: dict[str, str] = {
    "leave": "leave_policy",
    "higher_education": "education_policy",
    "nps": "nps_policy",
    "working_hours": "working_hours",
    "project_party": "project_party",
}


def _tag_for_file(filename: str) -> str:
    lower = filename.lower()
    for fragment, tag in FILE_TAGS.items():
        if fragment in lower:
            return tag
    return "general_policy"


def get_embeddings() -> CohereEmbeddings:
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=os.environ["COHERE_API_KEY"],
    )


def build_vector_store(
    docs_dir: str = POLICIES_DIR,
    persist_dir: str = CHROMA_DB_DIR,
) -> Chroma:
    """Load all PDFs, split into chunks, embed, and persist to Chroma."""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        raise FileNotFoundError(
            f"Policies directory not found: {docs_dir}\n"
            "Create it and add your PDF files."
        )

    pdf_files = list(docs_path.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {docs_dir}")

    print(f"📄 Loading {len(pdf_files)} PDF(s) from {docs_dir} …")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    for pdf_path in pdf_files:
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        chunks = splitter.split_documents(pages)
        tag = _tag_for_file(pdf_path.name)
        for chunk in chunks:
            chunk.metadata["source"] = pdf_path.name
            chunk.metadata["tag"] = tag
        all_chunks.extend(chunks)
        print(f"   ✅ {pdf_path.name}  →  {len(chunks)} chunks  (tag={tag})")

    print(f"\n🔢 Total chunks: {len(all_chunks)}")
    print("🔗 Building Chroma vector store with Cohere embeddings …")

    embeddings = get_embeddings()
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )

    print(f"✅ Vector store persisted at: {persist_dir}\n")
    return vectorstore


def load_vector_store(persist_dir: str = CHROMA_DB_DIR) -> Chroma:
    """Load an existing Chroma vector store from disk."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )


def get_or_build_vector_store() -> Chroma:
    """Return existing store or build a fresh one."""
    if Path(CHROMA_DB_DIR).exists():
        return load_vector_store()
    return build_vector_store()


if __name__ == "__main__":
    build_vector_store()
