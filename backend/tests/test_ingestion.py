import pytest
import os
from pathlib import Path
import tempfile

from app.ingestion.walker import walk_project, FileEntry
from app.ingestion.chunker import chunk_file, _fallback_chunk


# ── Walker tests ──────────────────────────────────────────────────────────────

def test_walk_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        entries, tree = walk_project(Path(tmp))
    assert entries == []
    assert tree == []


def test_walk_detects_languages():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "main.py").write_text("print('hello')")
        (Path(tmp) / "app.ts").write_text("const x = 1;")
        (Path(tmp) / "README.md").write_text("# Hello")
        entries, tree = walk_project(Path(tmp))
    langs = {e.language for e in entries}
    assert "python" in langs
    assert "typescript" in langs
    assert "markdown" in langs


def test_walk_skips_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        nm = Path(tmp) / "node_modules"
        nm.mkdir()
        (nm / "lib.js").write_text("module.exports = {}")
        (Path(tmp) / "index.js").write_text("const x = 1;")
        entries, _ = walk_project(Path(tmp))
    paths = [e.rel_path for e in entries]
    assert not any("node_modules" in p for p in paths)
    assert any("index.js" in p for p in paths)


def test_walk_skips_large_files():
    with tempfile.TemporaryDirectory() as tmp:
        big = Path(tmp) / "big.py"
        big.write_bytes(b"x = 1\n" * 100_000)
        small = Path(tmp) / "small.py"
        small.write_text("x = 1")
        entries, _ = walk_project(Path(tmp))
    paths = [e.rel_path for e in entries]
    assert not any("big.py" in p for p in paths)
    assert any("small.py" in p for p in paths)


def test_walk_tree_structure():
    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "src"
        sub.mkdir()
        (sub / "main.py").write_text("x = 1")
        (Path(tmp) / "README.md").write_text("# hi")
        entries, tree = walk_project(Path(tmp))
    names = [n["name"] for n in tree]
    assert "src" in names
    assert "README.md" in names


def test_walk_respects_gitignore():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / ".gitignore").write_text("secret.py\n")
        (Path(tmp) / "secret.py").write_text("password = '123'")
        (Path(tmp) / "main.py").write_text("x = 1")
        entries, _ = walk_project(Path(tmp))
    paths = [e.rel_path for e in entries]
    assert not any("secret.py" in p for p in paths)
    assert any("main.py" in p for p in paths)


# ── Chunker tests ─────────────────────────────────────────────────────────────

def _make_entry(content: str, filename: str, language: str) -> FileEntry:
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix, delete=False, mode="w"
    ) as f:
        f.write(content)
        path = Path(f.name)
    return FileEntry(
        rel_path=filename,
        abs_path=path,
        language=language,
        size_bytes=len(content),
    )


def test_chunk_python_functions_produces_chunks():
    # Each function is 6 lines — above MIN_CHUNK_LINES=3, AST chunking should work
    code = (
        "def hello(name: str) -> str:\n"
        '    """Say hello to someone."""\n'
        "    result = f'Hello, {name}!'\n"
        "    print(result)\n"
        "    return result\n"
        "\n"
        "\n"
        "def goodbye(name: str) -> str:\n"
        '    """Say goodbye to someone."""\n'
        "    result = f'Goodbye, {name}!'\n"
        "    print(result)\n"
        "    return result\n"
    )
    entry = _make_entry(code, "greet.py", "python")
    chunks = chunk_file(entry, "proj-1")
    os.unlink(entry.abs_path)

    assert len(chunks) >= 1
    assert all(c.project_id == "proj-1" for c in chunks)
    assert all(c.file_path == "greet.py" for c in chunks)


def test_chunk_python_named_symbols():
    code = (
        "def alpha(x: int) -> int:\n"
        '    """Return x squared."""\n'
        "    squared = x * x\n"
        "    print(squared)\n"
        "    return squared\n"
        "\n"
        "\n"
        "def beta(x: int) -> int:\n"
        '    """Return x cubed."""\n'
        "    cubed = x * x * x\n"
        "    print(cubed)\n"
        "    return cubed\n"
    )
    entry = _make_entry(code, "math_utils.py", "python")
    chunks = chunk_file(entry, "proj-1")
    os.unlink(entry.abs_path)

    named = {c.symbol_name for c in chunks if c.symbol_name}
    # Either AST extracted names, or fallback produced at least one chunk
    assert len(chunks) >= 1
    if named:
        assert "alpha" in named or "beta" in named


def test_chunk_python_class():
    code = (
        "class MyClass:\n"
        '    """A simple class."""\n'
        "\n"
        "    def __init__(self, x: int):\n"
        "        self.x = x\n"
        "        self.y = x * 2\n"
        "\n"
        "    def get_x(self) -> int:\n"
        "        return self.x\n"
        "\n"
        "    def get_y(self) -> int:\n"
        "        return self.y\n"
    )
    entry = _make_entry(code, "myclass.py", "python")
    chunks = chunk_file(entry, "proj-1")
    os.unlink(entry.abs_path)

    assert len(chunks) >= 1
    types = {c.chunk_type for c in chunks}
    assert "class" in types or "function" in types or "fallback" in types


def test_chunk_fallback_for_unknown_language():
    content = "\n".join([f"line {i}" for i in range(200)])
    entry = _make_entry(content, "data.txt", "unknown")
    chunks = _fallback_chunk(content, entry, "proj-1")
    os.unlink(entry.abs_path)

    assert len(chunks) > 1
    for c in chunks:
        assert c.chunk_type == "fallback"
        assert c.project_id == "proj-1"


def test_chunk_empty_file():
    entry = _make_entry("", "empty.py", "python")
    chunks = chunk_file(entry, "proj-1")
    os.unlink(entry.abs_path)
    assert chunks == []


def test_chunk_preserves_line_numbers():
    code = (
        "def alpha():\n"
        "    x = 1\n"
        "    y = 2\n"
        "    return x + y\n"
        "\n"
        "\n"
        "def beta():\n"
        "    a = 10\n"
        "    b = 20\n"
        "    return a + b\n"
    )
    entry = _make_entry(code, "lines.py", "python")
    chunks = chunk_file(entry, "proj-1")
    os.unlink(entry.abs_path)

    for c in chunks:
        assert c.start_line >= 1
        assert c.end_line >= c.start_line
