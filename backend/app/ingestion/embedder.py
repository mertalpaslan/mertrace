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
_embedding_dim: int = 0


def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (cached after first call)."""
    global _model, _embedding_dim
    if _model is None:
        logger.info("Loading embedding model", extra={"model": MODEL_NAME})
        _model = SentenceTransformer(MODEL_NAME)
        _embedding_dim = _model.get_sentence_embedding_dimension() or 0
        logger.info(
            "Embedding model loaded",
            extra={"model": MODEL_NAME, "dimensions": _embedding_dim},
        )
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

    # Log per-language breakdown
    lang_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for c in chunks:
        lang_counts[c.language] = lang_counts.get(c.language, 0) + 1
        type_counts[c.chunk_type] = type_counts.get(c.chunk_type, 0) + 1

    logger.info(
        "Embedding start",
        extra={
            "project_id": chunks[0].project_id,
            "total_chunks": total,
            "batches": (total + BATCH_SIZE - 1) // BATCH_SIZE,
            "model": MODEL_NAME,
            "dimensions": _embedding_dim,
            "by_language": lang_counts,
            "by_type": type_counts,
        },
    )

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.text for c in batch]
        ids = [c.id for c in batch]
        metadatas = [c.to_chroma_metadata() for c in batch]

        batch_t0 = time.monotonic()
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        batch_ms = int((time.monotonic() - batch_t0) * 1000)

        col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        embedded += len(batch)
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        logger.debug(
            f"Embedded batch {batch_num}/{total_batches}",
            extra={
                "batch": batch_num,
                "batch_size": len(batch),
                "embedded_so_far": embedded,
                "total": total,
                "batch_ms": batch_ms,
                "avg_ms_per_chunk": round(batch_ms / len(batch), 1),
            },
        )
        if progress_cb:
            progress_cb(embedded, total)

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Embedding complete",
        extra={
            "project_id": chunks[0].project_id,
            "total_chunks": total,
            "duration_ms": duration_ms,
            "chunks_per_sec": round(total / (duration_ms / 1000), 1) if duration_ms else 0,
            "collection": col.name,
        },
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

    t0 = time.monotonic()
    query_embedding = model.encode([query_text], show_progress_bar=False).tolist()
    embed_ms = int((time.monotonic() - t0) * 1000)

    kwargs: dict = {
        "query_embeddings": query_embedding,
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    t1 = time.monotonic()
    results = col.query(**kwargs)
    search_ms = int((time.monotonic() - t1) * 1000)

    output = []
    for doc, meta, dist, cid in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    ):
        output.append({"id": cid, "text": doc, "metadata": meta, "distance": dist})

    logger.debug(
        "Query embedding complete",
        extra={
            "project_id": project_id,
            "query_preview": query_text[:60],
            "results": len(output),
            "embed_ms": embed_ms,
            "search_ms": search_ms,
            "top_score": round(1.0 - output[0]["distance"], 4) if output else 0,
            "filter": where,
        },
    )
    return output
