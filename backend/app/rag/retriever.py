from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from app.ingestion.embedder import query_collection, collection_name
from app.core.logging import get_logger

logger = get_logger(__name__)

SEMANTIC_TOP_K = 20
BM25_TOP_K = 10
FUSION_TOP_K = 30


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    file_path: str
    language: str
    chunk_type: str
    symbol_name: Optional[str]
    start_line: int
    end_line: int
    score: float
    source: str  # "semantic" | "bm25" | "hybrid"


def retrieve(
    project_id: str,
    query: str,
    chroma_client: chromadb.ClientAPI,
    top_k: int = FUSION_TOP_K,
    language_filter: Optional[str] = None,
    file_filter: Optional[str] = None,
) -> list[RetrievedChunk]:
    """
    Hybrid retrieval: semantic search fused with BM25.
    Returns up to top_k deduplicated chunks ranked by reciprocal rank fusion.
    """
    where: dict | None = None
    if language_filter:
        where = {"language": language_filter}
    elif file_filter:
        where = {"file_path": {"$eq": file_filter}}

    # ── Semantic search ───────────────────────────────────────────────────────
    semantic_results = _semantic_search(
        project_id, query, chroma_client, SEMANTIC_TOP_K, where
    )

    # ── BM25 keyword search ───────────────────────────────────────────────────
    bm25_results = _bm25_search(
        project_id, query, chroma_client, BM25_TOP_K, where
    )

    # ── Reciprocal Rank Fusion ────────────────────────────────────────────────
    fused = _reciprocal_rank_fusion(
        [semantic_results, bm25_results], top_k=top_k
    )

    logger.debug(
        "Retrieval complete",
        extra={
            "project_id": project_id,
            "semantic": len(semantic_results),
            "bm25": len(bm25_results),
            "fused": len(fused),
        },
    )
    return fused


def _semantic_search(
    project_id: str,
    query: str,
    chroma_client: chromadb.ClientAPI,
    n: int,
    where: dict | None,
) -> list[RetrievedChunk]:
    try:
        raw = query_collection(
            project_id=project_id,
            query_text=query,
            chroma_client=chroma_client,
            n_results=n,
            where=where,
        )
    except Exception as e:
        logger.warning("Semantic search failed", extra={"error": str(e)})
        return []

    results = []
    for item in raw:
        meta = item["metadata"]
        results.append(RetrievedChunk(
            chunk_id=item["id"],
            text=item["text"],
            file_path=meta.get("file_path", ""),
            language=meta.get("language", "unknown"),
            chunk_type=meta.get("chunk_type", "unknown"),
            symbol_name=meta.get("symbol_name") or None,
            start_line=int(meta.get("start_line", 0)),
            end_line=int(meta.get("end_line", 0)),
            score=1.0 - float(item["distance"]),
            source="semantic",
        ))
    return results


def _bm25_search(
    project_id: str,
    query: str,
    chroma_client: chromadb.ClientAPI,
    n: int,
    where: dict | None,
) -> list[RetrievedChunk]:
    """Fetch all docs from ChromaDB and run BM25 locally."""
    try:
        col = chroma_client.get_collection(collection_name(project_id))
        count = col.count()
        if count == 0:
            return []

        # Fetch all documents (cap at 5000 for memory)
        limit = min(count, 5000)
        result = col.get(
            limit=limit,
            include=["documents", "metadatas"],
            where=where,
        )
        docs = result["documents"]
        metas = result["metadatas"]
        ids = result["ids"]
    except Exception as e:
        logger.warning("BM25 fetch failed", extra={"error": str(e)})
        return []

    if not docs:
        return []

    tokenized = [doc.lower().split() for doc in docs]
    bm25 = BM25Okapi(tokenized)
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    # Get top-n indices
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        meta = metas[idx]
        results.append(RetrievedChunk(
            chunk_id=ids[idx],
            text=docs[idx],
            file_path=meta.get("file_path", ""),
            language=meta.get("language", "unknown"),
            chunk_type=meta.get("chunk_type", "unknown"),
            symbol_name=meta.get("symbol_name") or None,
            start_line=int(meta.get("start_line", 0)),
            end_line=int(meta.get("end_line", 0)),
            score=float(scores[idx]),
            source="bm25",
        ))
    return results


def _reciprocal_rank_fusion(
    result_lists: list[list[RetrievedChunk]],
    top_k: int,
    k: int = 60,
) -> list[RetrievedChunk]:
    """Merge multiple ranked lists using RRF. Deduplicates by chunk_id."""
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}

    for result_list in result_lists:
        for rank, chunk in enumerate(result_list):
            rrf_scores[chunk.chunk_id] = (
                rrf_scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            )
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = chunk

    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

    fused = []
    for cid in sorted_ids[:top_k]:
        chunk = chunk_map[cid]
        chunk.score = rrf_scores[cid]
        chunk.source = "hybrid"
        fused.append(chunk)
    return fused
