from __future__ import annotations

from app.rag.retriever import RetrievedChunk
from app.core.logging import get_logger

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
        logger.debug("Reranker unavailable, using retrieval order")
        return chunks[:top_k]

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

        logger.debug(
            "Reranking complete",
            extra={"input": len(chunks), "output": len(reranked)},
        )
        return reranked

    except Exception as e:
        logger.warning("Reranking failed, using retrieval order", extra={"error": str(e)})
        return chunks[:top_k]
