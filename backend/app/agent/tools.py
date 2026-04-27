from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import chromadb

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.embedder import query_collection

logger = get_logger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    tool_input: dict
    output: Any
    duration_ms: int
    error: str | None = None

    def to_ws_payload(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.output,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    fn: Callable


# ── Tool implementations ──────────────────────────────────────────────────────

def search_code(
    query: str,
    project_id: str,
    chroma_client: chromadb.ClientAPI,
    n_results: int = 10,
    language: str | None = None,
) -> list[dict]:
    """Semantic search over indexed code chunks."""
    where = {"language": language} if language else None
    results = query_collection(
        project_id=project_id,
        query_text=query,
        chroma_client=chroma_client,
        n_results=n_results,
        where=where,
    )
    return [
        {
            "chunk_id": r["id"],
            "file_path": r["metadata"].get("file_path", ""),
            "symbol_name": r["metadata"].get("symbol_name", ""),
            "chunk_type": r["metadata"].get("chunk_type", ""),
            "start_line": r["metadata"].get("start_line", 0),
            "end_line": r["metadata"].get("end_line", 0),
            "language": r["metadata"].get("language", ""),
            "score": round(1.0 - float(r["distance"]), 4),
            "text": r["text"][:300],
        }
        for r in results
    ]


def read_file(
    file_path: str,
    project_id: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> dict:
    """Read a file from the project directory, optionally sliced by line range."""
    base = (Path(settings.projects_tmp_dir) / project_id).resolve()
    target = (base / file_path).resolve()

    if not str(target).startswith(str(base)):
        return {"error": "Access denied — path outside project directory"}
    if not target.exists():
        return {"error": f"File not found: {file_path}"}
    if not target.is_file():
        return {"error": f"Not a file: {file_path}"}

    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        s = max(0, start_line - 1)
        e = min(total, end_line) if end_line else total
        sliced = lines[s:e]
        return {
            "file_path": file_path,
            "start_line": s + 1,
            "end_line": s + len(sliced),
            "total_lines": total,
            "content": "\n".join(sliced),
        }
    except Exception as ex:
        return {"error": str(ex)}


def grep_symbol(
    symbol: str,
    project_id: str,
    file_extension: str | None = None,
) -> list[dict]:
    """Search for a symbol name (function/class/variable) across all project files."""
    base = Path(settings.projects_tmp_dir) / project_id
    if not base.exists():
        return [{"error": "Project directory not found"}]

    pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
    matches = []

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if file_extension and path.suffix != file_extension:
            continue
        # Skip binary / large files
        if path.stat().st_size > 512 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    matches.append({
                        "file_path": str(path.relative_to(base)),
                        "line": i,
                        "text": line.strip()[:200],
                    })
                    if len(matches) >= 50:
                        return matches
        except Exception:
            continue
    return matches


def list_files(
    project_id: str,
    directory: str = "",
    language: str | None = None,
) -> list[dict]:
    """List files in the project, optionally filtered by directory or language."""
    data_dir = Path(settings.projects_data_dir) / project_id / "file_tree.json"
    if not data_dir.exists():
        return [{"error": "File tree not yet generated"}]

    tree = json.loads(data_dir.read_text())
    flat = _flatten_tree(tree)

    if directory:
        flat = [f for f in flat if f["path"].startswith(directory)]
    if language:
        flat = [f for f in flat if f.get("language") == language]

    return flat[:100]  # cap at 100


def _flatten_tree(nodes: list[dict], result: list | None = None) -> list[dict]:
    if result is None:
        result = []
    for node in nodes:
        if node["type"] == "file":
            result.append({
                "path": node["path"],
                "name": node["name"],
                "language": node.get("language", "unknown"),
            })
        elif node["type"] == "directory" and "children" in node:
            _flatten_tree(node["children"], result)
    return result


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "search_code",
        "description": "Semantic search over indexed code chunks. Use for finding relevant functions, classes, or logic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "n_results": {"type": "integer", "default": 10, "description": "Number of results"},
                "language": {"type": "string", "description": "Filter by language (python, typescript, go, etc.)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the full content of a file, or a specific line range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to the file"},
                "start_line": {"type": "integer", "default": 1},
                "end_line": {"type": "integer", "description": "Last line to read (inclusive)"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "grep_symbol",
        "description": "Find all occurrences of a symbol name (function, class, variable) across the codebase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to search for"},
                "file_extension": {"type": "string", "description": "Filter by extension e.g. .py .ts"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in the project, optionally filtered by directory or language.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "default": "", "description": "Directory prefix to filter"},
                "language": {"type": "string", "description": "Filter by language"},
            },
        },
    },
]


def run_tool(
    tool_name: str,
    tool_input: dict,
    project_id: str,
    chroma_client: chromadb.ClientAPI,
) -> ToolResult:
    """Dispatch a tool call and return a ToolResult."""
    t0 = time.monotonic()
    error = None
    output: Any = None

    try:
        if tool_name == "search_code":
            output = search_code(
                query=tool_input["query"],
                project_id=project_id,
                chroma_client=chroma_client,
                n_results=tool_input.get("n_results", 10),
                language=tool_input.get("language"),
            )
        elif tool_name == "read_file":
            output = read_file(
                file_path=tool_input["file_path"],
                project_id=project_id,
                start_line=tool_input.get("start_line", 1),
                end_line=tool_input.get("end_line"),
            )
        elif tool_name == "grep_symbol":
            output = grep_symbol(
                symbol=tool_input["symbol"],
                project_id=project_id,
                file_extension=tool_input.get("file_extension"),
            )
        elif tool_name == "list_files":
            output = list_files(
                project_id=project_id,
                directory=tool_input.get("directory", ""),
                language=tool_input.get("language"),
            )
        else:
            error = f"Unknown tool: {tool_name}"
            output = []
    except Exception as e:
        error = str(e)
        output = []
        logger.error("Tool error", extra={"tool": tool_name, "error": str(e)})

    duration_ms = int((time.monotonic() - t0) * 1000)
    return ToolResult(
        tool_name=tool_name,
        tool_input=tool_input,
        output=output,
        duration_ms=duration_ms,
        error=error,
    )
