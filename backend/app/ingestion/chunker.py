from __future__ import annotations

import re
from typing import Optional

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_go as tsgo
from tree_sitter import Language, Parser, Node

from app.models.chunk import Chunk
from app.ingestion.walker import FileEntry
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_CHUNK_LINES = 80
MIN_CHUNK_LINES = 3

# Build language objects once at import time
_LANGUAGES: dict[str, Language] = {
    "python": Language(tspython.language()),
    "javascript": Language(tsjavascript.language()),
    "typescript": Language(tstypescript.language_typescript()),
    "go": Language(tsgo.language()),
}

# Node types that represent top-level symbols per language
_SYMBOL_NODES: dict[str, set[str]] = {
    "python": {"function_definition", "class_definition", "decorated_definition"},
    "javascript": {"function_declaration", "class_declaration", "method_definition",
                   "arrow_function", "export_statement"},
    "typescript": {"function_declaration", "class_declaration", "method_definition",
                   "interface_declaration", "type_alias_declaration", "export_statement"},
    "go": {"function_declaration", "method_declaration", "type_declaration"},
}


def chunk_file(entry: FileEntry, project_id: str) -> list[Chunk]:
    """
    Parse a file with tree-sitter (if supported) and return a list of Chunks.
    Falls back to line-window chunking for unsupported languages.
    """
    text = entry.read_text()
    if text is None:
        return []

    lang = entry.language
    if lang in _LANGUAGES:
        try:
            return _ast_chunk(text, entry, project_id)
        except Exception as e:
            logger.warning(
                "AST chunking failed, falling back",
                extra={"path": entry.rel_path, "error": str(e)},
            )

    return _fallback_chunk(text, entry, project_id)


def _ast_chunk(text: str, entry: FileEntry, project_id: str) -> list[Chunk]:
    """Extract top-level symbols using tree-sitter."""
    lang_obj = _LANGUAGES[entry.language]
    parser = Parser(lang_obj)
    tree = parser.parse(text.encode("utf-8"))
    root = tree.root_node

    symbol_types = _SYMBOL_NODES.get(entry.language, set())
    chunks: list[Chunk] = []
    lines = text.splitlines()

    # Collect import block first
    import_chunk = _extract_imports(lines, entry, project_id)
    if import_chunk:
        chunks.append(import_chunk)

    # Walk top-level nodes
    for node in root.children:
        if node.type in symbol_types:
            chunk = _node_to_chunk(node, lines, text, entry, project_id)
            if chunk:
                chunks.append(chunk)
        # Handle nested (e.g. class body methods)
        elif node.type in ("class_definition", "class_declaration"):
            class_chunk = _node_to_chunk(node, lines, text, entry, project_id)
            if class_chunk:
                chunks.append(class_chunk)
            for child in node.children:
                if child.type in ("block", "class_body"):
                    for method in child.children:
                        if method.type in symbol_types:
                            m_chunk = _node_to_chunk(
                                method, lines, text, entry, project_id,
                                parent_class=_get_name(node, text),
                            )
                            if m_chunk:
                                chunks.append(m_chunk)

    if not chunks:
        return _fallback_chunk(text, entry, project_id)
    return chunks


def _node_to_chunk(
    node: Node,
    lines: list[str],
    text: str,
    entry: FileEntry,
    project_id: str,
    parent_class: Optional[str] = None,
) -> Optional[Chunk]:
    start_line = node.start_point[0]
    end_line = node.end_point[0]

    if (end_line - start_line) < MIN_CHUNK_LINES:
        return None

    chunk_lines = lines[start_line : end_line + 1]
    chunk_text = "\n".join(chunk_lines)

    name = _get_name(node, text)
    chunk_type = _classify_node(node.type, entry.language)
    docstring = _extract_docstring(chunk_lines)

    return Chunk(
        text=chunk_text,
        file_path=entry.rel_path,
        chunk_type=chunk_type,
        symbol_name=name,
        parent_class=parent_class,
        start_line=start_line + 1,
        end_line=end_line + 1,
        language=entry.language,
        docstring=docstring,
        project_id=project_id,
    )


def _fallback_chunk(text: str, entry: FileEntry, project_id: str) -> list[Chunk]:
    """Sliding window chunker for unsupported languages."""
    lines = text.splitlines()
    chunks: list[Chunk] = []
    step = MAX_CHUNK_LINES // 2

    for start in range(0, len(lines), step):
        end = min(start + MAX_CHUNK_LINES, len(lines))
        window = lines[start:end]
        if len(window) < MIN_CHUNK_LINES:
            break
        chunks.append(Chunk(
            text="\n".join(window),
            file_path=entry.rel_path,
            chunk_type="fallback",
            start_line=start + 1,
            end_line=end,
            language=entry.language,
            project_id=project_id,
        ))
        if end == len(lines):
            break
    return chunks


def _extract_imports(lines: list[str], entry: FileEntry, project_id: str) -> Optional[Chunk]:
    """Collect contiguous import lines at the top of the file."""
    import_lines = []
    for i, line in enumerate(lines[:50]):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "require(", "use ")):
            import_lines.append((i, line))
        elif import_lines and stripped == "":
            continue
        elif import_lines:
            break

    if len(import_lines) < 2:
        return None

    start = import_lines[0][0]
    end = import_lines[-1][0]
    return Chunk(
        text="\n".join(l for _, l in import_lines),
        file_path=entry.rel_path,
        chunk_type="import",
        start_line=start + 1,
        end_line=end + 1,
        language=entry.language,
        project_id=project_id,
    )


def _get_name(node: Node, text: str) -> Optional[str]:
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "type_identifier"):
            return text[child.start_byte:child.end_byte]
    return None


def _classify_node(node_type: str, language: str) -> str:
    if "class" in node_type:
        return "class"
    if "method" in node_type:
        return "method"
    if "function" in node_type or "arrow" in node_type:
        return "function"
    if "interface" in node_type or "type_alias" in node_type:
        return "class"
    return "function"


def _extract_docstring(lines: list[str]) -> Optional[str]:
    """Extract first docstring/comment block from chunk lines."""
    joined = "\n".join(lines[:10])
    # Python triple-quote
    m = re.search(r'"""(.+?)"""', joined, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    m = re.search(r"'''(.+?)'''", joined, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    # JS/TS block comment
    m = re.search(r"/\*\*?(.+?)\*/", joined, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return None
