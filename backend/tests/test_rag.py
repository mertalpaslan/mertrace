import pytest
from unittest.mock import MagicMock, patch

from app.rag.retriever import (
    RetrievedChunk,
    _reciprocal_rank_fusion,
    _bm25_search,
)
from app.rag.reranker import rerank
from app.rag.context_assembler import assemble, AssembledContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_chunk(chunk_id: str, text: str, score: float = 0.9,
               file_path: str = "src/main.py", start_line: int = 1,
               end_line: int = 10, language: str = "python",
               chunk_type: str = "function", symbol_name: str = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        symbol_name=symbol_name,
        start_line=start_line,
        end_line=end_line,
        score=score,
        source="semantic",
    )


# ── RRF tests ─────────────────────────────────────────────────────────────────

def test_rrf_deduplicates():
    a = make_chunk("c1", "def foo(): pass")
    b = make_chunk("c1", "def foo(): pass")  # same id
    c = make_chunk("c2", "def bar(): pass")

    result = _reciprocal_rank_fusion([[a, c], [b]], top_k=10)
    ids = [r.chunk_id for r in result]
    assert ids.count("c1") == 1
    assert "c2" in ids


def test_rrf_boosts_appearing_in_both_lists():
    shared = make_chunk("shared", "def shared(): pass")
    only_semantic = make_chunk("sem_only", "def sem(): pass")
    only_bm25 = make_chunk("bm25_only", "def bm25(): pass")

    result = _reciprocal_rank_fusion(
        [[shared, only_semantic], [shared, only_bm25]], top_k=10
    )
    ids = [r.chunk_id for r in result]
    # shared appears in both lists so should rank first
    assert ids[0] == "shared"


def test_rrf_respects_top_k():
    chunks = [make_chunk(f"c{i}", f"def f{i}(): pass") for i in range(20)]
    result = _reciprocal_rank_fusion([chunks], top_k=5)
    assert len(result) == 5


def test_rrf_empty_lists():
    result = _reciprocal_rank_fusion([[], []], top_k=10)
    assert result == []


# ── Reranker tests ────────────────────────────────────────────────────────────

def test_rerank_returns_top_k():
    chunks = [make_chunk(f"c{i}", f"def func_{i}(): return {i}") for i in range(15)]
    # FlashRank may not be installed in CI — reranker falls back gracefully
    result = rerank("what does func_5 do", chunks, top_k=5)
    assert len(result) <= 5
    assert len(result) >= 1


def test_rerank_empty_input():
    result = rerank("query", [], top_k=5)
    assert result == []


def test_rerank_fewer_than_top_k():
    chunks = [make_chunk("c1", "def foo(): pass")]
    result = rerank("foo function", chunks, top_k=10)
    assert len(result) == 1


# ── Context assembler tests ───────────────────────────────────────────────────

def test_assemble_empty_chunks():
    ctx = assemble("query", [])
    assert ctx.total_chunks == 0
    assert ctx.citations == []
    assert "No relevant" in ctx.context_text


def test_assemble_includes_all_chunks_within_budget():
    chunks = [
        make_chunk("c1", "def alpha(): pass", file_path="a.py"),
        make_chunk("c2", "def beta(): pass", file_path="b.py"),
        make_chunk("c3", "def gamma(): pass", file_path="a.py"),
    ]
    ctx = assemble("query", chunks, max_tokens=2000)
    assert ctx.total_chunks == 3
    assert len(ctx.citations) == 3


def test_assemble_respects_token_budget():
    # Each chunk is ~1000 chars, budget is 100 tokens (~350 chars)
    big_text = "x = 1\n" * 200  # ~1200 chars
    chunks = [make_chunk(f"c{i}", big_text) for i in range(5)]
    ctx = assemble("query", chunks, max_tokens=100)
    # Should include at most 1 chunk (or truncated)
    assert ctx.total_chunks <= 2


def test_assemble_groups_by_file():
    chunks = [
        make_chunk("c1", "def a(): pass", file_path="utils.py", start_line=1),
        make_chunk("c2", "def b(): pass", file_path="utils.py", start_line=10),
        make_chunk("c3", "def c(): pass", file_path="main.py", start_line=1),
    ]
    ctx = assemble("query", chunks)
    # utils.py should appear once as a header
    assert ctx.context_text.count("utils.py") >= 1
    assert ctx.context_text.count("main.py") >= 1


def test_assemble_citations_have_correct_fields():
    chunk = make_chunk(
        "c1", "def foo(): pass",
        file_path="src/foo.py", start_line=5, end_line=10,
        symbol_name="foo",
    )
    ctx = assemble("query", [chunk])
    assert len(ctx.citations) == 1
    cit = ctx.citations[0]
    assert cit.file_path == "src/foo.py"
    assert cit.start_line == 5
    assert cit.end_line == 10
    assert cit.symbol_name == "foo"
    assert cit.index == 1


def test_assemble_context_contains_language_fence():
    chunk = make_chunk("c1", "def foo(): pass", language="python")
    ctx = assemble("query", [chunk])
    assert "```python" in ctx.context_text
