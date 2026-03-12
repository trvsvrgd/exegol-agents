"""Chroma-based vector store for Coordinator memory: past decisions and SOPs."""

import logging
from pathlib import Path
from typing import Any

import yaml
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Persist to project data dir; create if missing
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "agents.yaml"
MEMORY_DIR = PROJECT_ROOT / "data" / "exegol_memory"
COLLECTION_NAME = "exegol_coordinator_memory"

# Document type metadata
TYPE_ARCHITECTURAL_DECISION = "architectural_decision"
TYPE_SOP = "sop"

_embedding_model: str | None = None
_vector_store: Chroma | None = None


def _load_embedding_config() -> str:
    """Load embedding model from config/agents.yaml if present."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    if not CONFIG_PATH.exists():
        _embedding_model = "nomic-embed-text"
        return _embedding_model
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        memory = data.get("memory", {})
        _embedding_model = memory.get("embedding_model", "nomic-embed-text")
        return _embedding_model
    except Exception:
        _embedding_model = "nomic-embed-text"
        return _embedding_model


def get_memory_store() -> Chroma:
    """Return or create the persistent Chroma vector store."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    model = _load_embedding_config()
    embeddings = OllamaEmbeddings(
        model=model,
        base_url="http://localhost:11434",
    )
    _vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(MEMORY_DIR),
    )
    return _vector_store


def add_to_memory(
    content: str,
    doc_type: str = TYPE_ARCHITECTURAL_DECISION,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Add a document to the Coordinator's memory.
    doc_type: 'architectural_decision' or 'sop'
    """
    try:
        store = get_memory_store()
        meta = {"doc_type": doc_type, **(metadata or {})}
        store.add_documents([Document(page_content=content, metadata=meta)])
        logger.info("Added %s to memory: %s...", doc_type, content[:80])
    except Exception as e:
        logger.warning("Failed to add to memory: %s", e)


def retrieve_relevant(
    query: str,
    k: int = 5,
    doc_types: list[str] | None = None,
) -> str:
    """
    Retrieve relevant past decisions and SOPs for the Coordinator.
    Returns formatted string for injection into the Router prompt.
    """
    try:
        store = get_memory_store()
        filter_arg: dict | None = None
        if doc_types:
            filter_arg = {"doc_type": {"$in": doc_types}}
        docs = store.similarity_search(query, k=k, filter=filter_arg)
        if not docs:
            return ""
        lines = [
            f"- [{d.metadata.get('doc_type', 'decision')}] {d.page_content[:500]}"
            + ("..." if len(d.page_content) > 500 else "")
            for d in docs
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning("Memory retrieval failed: %s", e)
        return ""
