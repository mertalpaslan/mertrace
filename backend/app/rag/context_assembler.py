from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.rag.retriever import RetrievedChunk
from app.models.chunk import Citation
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Conservative token budget — leaves room for system prompt + response
MAX_CONTEXT_TOKENS = 6000
# Rough chars-per-token estimate for code (code is denser than prose)
CHARS_PER_TOKEN = 3.5


@dataclass
class AssembledContext:
    context_text: str
    citations: list[Citation]
    total_chunks: int
    estimated_tokens: int


def assemble(
    query: str,
    chunks: list[RetrievedChunk],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> AssembledContext:
    """
    Pack chunks into a context string within the token budget.
    Builds citation list for source attribution.
    Groups chunks by file for readability.
    """
    if not chunks:
        return AssembledContext(
            context_text="No relevant code found.",
            citations=[],
            total_chunks=0,
            estimated_tokens=0,
        )

    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    used_chars = 0
    selected: list[RetrievedChunk] = []

    for chunk in chunks:
        chunk_chars = len(chunk.text) + 100  # +100 for header overhead
        if used_chars + chunk_chars > max_chars:
            break
        selected.append(chunk)
        used_chars += chunk_chars

    if not selected:
        # At minimum include the top chunk truncated
        top = chunks[0]
        truncated = top.text[: int(max_chars * 0.8)]
        selected_text = _format_chunk(top, truncated)
        return AssembledContext(
            context_text=selected_text,
            citations=[_make_citation(top, 1)],
            total_chunks=1,
            estimated_tokens=int(len(selected_text) / CHARS_PER_TOKEN),
        )

    # Group by file path for cleaner context
    by_file: dict[str, list[RetrievedChunk]] = {}
    for chunk in selected:
        by_file.setdefault(chunk.file_path, []).append(chunk)

    parts: list[str] = []
    citations: list[Citation] = []
    citation_idx = 1

    for file_path, file_chunks in by_file.items():
        # Sort chunks within file by line number
        file_chunks.sort(key=lambda c: c.start_line)
        parts.append(f"### File: `{file_path}`")

        for chunk in file_chunks:
            parts.append(_format_chunk(chunk, chunk.text))
            citations.append(_make_citation(chunk, citation_idx))
            citation_idx += 1

    context_text = "\n\n".join(parts)
    estimated_tokens = int(len(context_text) / CHARS_PER_TOKEN)

    logger.info(
        "Context assembled",
        extra={
            "chunks_selected": len(selected),
            "chunks_dropped": len(chunks) - len(selected),
            "files": len(by_file),
            "estimated_tokens": estimated_tokens,
            "token_budget": max_tokens,
            "budget_used_pct": round(estimated_tokens / max_tokens * 100, 1),
            "top_files": list(by_file.keys())[:5],
            "chunk_types": {
                ct: sum(1 for c in selected if c.chunk_type == ct)
                for ct in {c.chunk_type for c in selected}
            },
        },
    )
    if settings.debug:
        _log_context_pretty(context_text, citations, estimated_tokens, max_tokens)

    return AssembledContext(
        context_text=context_text,
        citations=citations,
        total_chunks=len(selected),
        estimated_tokens=estimated_tokens,
    )


def _format_chunk(chunk: RetrievedChunk, text: str) -> str:
    """Format a single chunk with a header showing location and type."""
    symbol = f" — `{chunk.symbol_name}`" if chunk.symbol_name else ""
    header = (
        f"```{chunk.language}\n"
        f"# {chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        f" ({chunk.chunk_type}{symbol})\n"
    )
    return header + text + "\n```"


def _log_context_pretty(
    context_text: str,
    citations: list[Citation],
    estimated_tokens: int,
    max_tokens: int,
) -> None:
    from app.core.logging import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW
    sep = "─" * 60
    lines = [
        f"{BOLD}{CYAN}┌─ CONTEXT SENT TO LLM ─ {estimated_tokens}/{max_tokens} tokens{RESET}",
        f"{CYAN}│{RESET} {sep}",
    ]
    for cit in citations:
        symbol = f" {cit.symbol_name}" if cit.symbol_name else ""
        lines.append(
            f"{CYAN}│{RESET} {YELLOW}[{cit.index}]{RESET} "
            f"{GREEN}{cit.file_path}:{cit.start_line}-{cit.end_line}{RESET}"
            f"{MAGENTA}{symbol}{RESET} "
            f"{DIM}({cit.chunk_type}){RESET}"
        )
    lines.append(f"{CYAN}│{RESET} {sep}")
    # Show first 800 chars of context
    preview = context_text[:800].replace("\n", "\n" + f"{CYAN}│{RESET} ")
    lines.append(f"{CYAN}│{RESET} {DIM}{preview}{RESET}")
    if len(context_text) > 800:
        lines.append(f"{CYAN}│{RESET} {DIM}... ({len(context_text)} chars total){RESET}")
    lines.append(f"{CYAN}└{'─' * 62}{RESET}")
    print("\n".join(lines), flush=True)


def _make_citation(chunk: RetrievedChunk, idx: int) -> Citation:
    return Citation(
        index=idx,
        file_path=chunk.file_path,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        symbol_name=chunk.symbol_name,
        chunk_type=chunk.chunk_type,
    )
