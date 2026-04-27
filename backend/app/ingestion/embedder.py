from __future__ import annotations

import time
from typing import Callable

from sentence_transformers import SentenceTransformer
import chromadb

from app.models.chunk import Chunk
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 64
COLLECTION_PREFIX = "project_"

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (cached after first call)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model", extra={"model": MODEL_NAME})
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
    return _model


def collection_name(project_id: str) -> str:
    return f"{COLLECTION_PREFIX}{project_id.replace('-', '_')}"


def embed_chunks(
    chunks: list[Chunk],
    chroma_client: chromadb.ClientAPI,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    """
    Embed all chunks and upsert into ChromaDB.
    Returns total number of chunks embedded.
    """
    if not chunks:
        return 0

    model = get_model()
    col = chroma_client.get_or_create_collection(
        name=collection_name(chunks[0].project_id),
        metadata={"hnsw:space": "cosine"},
    )

    total = len(chunks)
    embedded = 0
    t0 = time.monotonic()

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.text for c in batch]
        ids = [c.id for c in batch]
        metadatas = [c.to_chroma_metadata() for c in batch]

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        embedded += len(batch)
        if progress_cb:
            progress_cb(embedded, total)

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Embedding complete",
        extra={"total": total, "duration_ms": duration_ms},
    )
    return embedded


def delete_collection(project_id: str, chroma_client: chromadb.ClientAPI) -> None:
    """Delete the ChromaDB collection for a project."""
    name = collection_name(project_id)
    try:
        chroma_client.delete_collection(name)
        logger.info("Deleted collection", extra={"collection": name})
    except Exception as e:
        logger.warning("Could not delete collection", extra={"collection": name, "error": str(e)})


def query_collection(
    project_id: str,
    query_text: str,
    chroma_client: chromadb.ClientAPI,
    n_results: int = 20,
    where: dict | None = None,
) -> list[dict]:
    """
    Semantic search against a project's ChromaDB collection.
    Returns list of result dicts with text, metadata, distance.
    """
    model = get_model()
    col = chroma_client.get_collection(collection_name(project_id))

    query_embedding = model.encode([query_text], show_progress_bar=False).tolist()

    kwargs: dict = {"query_embeddings": query_embedding, "n_results": n_results,
                   "include": ["documents", "metadatas", "distances"]}
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

    output = []
    for doc, meta, dist, cid in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    ):
        output.append({"id": cid, "text": doc, "metadata": meta, "distance": dist})
    return output
