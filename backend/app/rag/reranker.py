from __future__ import annotations

import time
from app.rag.retriever import RetrievedChunk
from app.core.logging import get_logger, log_retrieval

logger = get_logger(__name__)

RERANK_TOP_K = 10

_reranker = None


def get_reranker():
    """Lazy-load FlashRank reranker (cached after first call)."""
    global _reranker
    if _reranker is None:
        try:
            from flashrank import Ranker
            _reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank")
            logger.info("FlashRank reranker loaded")
        except Exception as e:
            logger.warning("FlashRank unavailable, skipping rerank", extra={"error": str(e)})
            _reranker = False  # sentinel: tried and failed
    return _reranker if _reranker is not False else None


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int = RERANK_TOP_K,
) -> list[RetrievedChunk]:
    """
    Rerank retrieved chunks using FlashRank cross-encoder.
    Falls back to original order if FlashRank is unavailable.
    Returns top_k chunks.
    """
    if not chunks:
        return []

    ranker = get_reranker()
    if ranker is None:
        logger.info(
            "Reranker unavailable — using retrieval order",
            extra={"input": len(chunks), "top_k": top_k},
        )
        result = chunks[:top_k]
        _log_rerank_result(query, chunks, result)
        return result

    try:
        from flashrank import RerankRequest
        passages = [
            {"id": i, "text": chunk.text}
            for i, chunk in enumerate(chunks)
        ]
        request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(request)

        # results is sorted by score descending
        reranked = []
        for r in results[:top_k]:
            chunk = chunks[r["id"]]
            chunk.score = float(r["score"])
            reranked.append(chunk)

        _log_rerank_result(query, chunks, reranked)
        return reranked

    except Exception as e:
        logger.warning("Reranking failed, using retrieval order", extra={"error": str(e)})
        result = chunks[:top_k]
        _log_rerank_result(query, chunks, result)
        return result


def _log_rerank_result(
    query: str,
    before: list[RetrievedChunk],
    after: list[RetrievedChunk],
) -> None:
    top_chunks = [
        {
            "file_path": c.file_path,
            "start_line": c.start_line,
            "symbol_name": c.symbol_name,
            "chunk_type": c.chunk_type,
            "score": c.score,
            "text": c.text,
        }
        for c in after
    ]
    log_retrieval(
        project_id=after[0].file_path.split("/")[0] if after else "unknown",
        query=query,
        semantic_count=len([c for c in before if c.source == "semantic"]),
        bm25_count=len([c for c in before if c.source == "bm25"]),
        fused_count=len(before),
        reranked_count=len(after),
        top_chunks=top_chunks,
    )
