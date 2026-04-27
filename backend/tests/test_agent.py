import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agent.memory import ConversationMemory, get_memory, clear_memory
from app.agent.tools import (
    read_file, grep_symbol, list_files, _flatten_tree, run_tool
)


# ── Memory tests ──────────────────────────────────────────────────────────────

def test_memory_add_and_retrieve():
    mem = ConversationMemory(project_id="test")
    mem.add_user("What does foo do?")
    mem.add_assistant("foo returns bar.")
    msgs = mem.to_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_memory_trim_by_turns():
    mem = ConversationMemory(project_id="test")
    for i in range(25):
        mem.add_user(f"question {i}")
        mem.add_assistant(f"answer {i}")
    # Should be trimmed to MAX_TURNS * 2 = 40 entries
    assert len(mem.turns) <= 40
    # Should always start with user turn
    assert mem.turns[0].role == "user"


def test_memory_to_messages_max_turns():
    mem = ConversationMemory(project_id="test")
    for i in range(10):
        mem.add_user(f"q{i}")
        mem.add_assistant(f"a{i}")
    msgs = mem.to_messages(max_turns=3)
    assert len(msgs) <= 6


def test_memory_clear():
    mem = ConversationMemory(project_id="test")
    mem.add_user("hello")
    mem.add_assistant("hi")
    mem.clear()
    assert mem.turn_count == 0
    assert mem.turns == []


def test_memory_store_isolation():
    clear_memory("proj-a")
    clear_memory("proj-b")
    m1 = get_memory("proj-a")
    m2 = get_memory("proj-b")
    m1.add_user("only in a")
    assert m2.turn_count == 0


# ── Tool: read_file ───────────────────────────────────────────────────────────

def test_read_file_full():
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_dir = Path(tmp) / proj_id
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("line1\nline2\nline3\n")

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            result = read_file("main.py", proj_id)

    assert result["content"] == "line1\nline2\nline3"
    assert result["total_lines"] == 3


def test_read_file_line_range():
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_dir = Path(tmp) / proj_id
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("a\nb\nc\nd\ne\n")

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            result = read_file("main.py", proj_id, start_line=2, end_line=4)

    assert result["content"] == "b\nc\nd"
    assert result["start_line"] == 2


def test_read_file_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            result = read_file("nonexistent.py", "proj")
    assert "error" in result


def test_read_file_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            result = read_file("../../etc/passwd", "proj")
    assert "error" in result


# ── Tool: grep_symbol ─────────────────────────────────────────────────────────

def test_grep_symbol_finds_matches():
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_dir = Path(tmp) / proj_id
        proj_dir.mkdir()
        (proj_dir / "utils.py").write_text("def my_func():\n    pass\n")
        (proj_dir / "main.py").write_text("from utils import my_func\nmy_func()\n")

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            results = grep_symbol("my_func", proj_id)

    assert len(results) >= 2
    paths = [r["file_path"] for r in results]
    assert any("utils.py" in p for p in paths)
    assert any("main.py" in p for p in paths)


def test_grep_symbol_no_matches():
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_dir = Path(tmp) / proj_id
        proj_dir.mkdir()
        (proj_dir / "main.py").write_text("x = 1\n")

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            results = grep_symbol("nonexistent_symbol", proj_id)

    assert results == []


# ── Tool: list_files ──────────────────────────────────────────────────────────

def test_list_files_from_tree():
    import json
    tree = [
        {"name": "src", "path": "src", "type": "directory", "children": [
            {"name": "main.py", "path": "src/main.py", "type": "file", "language": "python"},
            {"name": "utils.py", "path": "src/utils.py", "type": "file", "language": "python"},
        ]},
        {"name": "README.md", "path": "README.md", "type": "file", "language": "markdown"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_data = Path(tmp) / proj_id
        proj_data.mkdir()
        (proj_data / "file_tree.json").write_text(json.dumps(tree))

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_data_dir = tmp
            results = list_files(proj_id)

    assert len(results) == 3
    paths = [r["path"] for r in results]
    assert "src/main.py" in paths
    assert "README.md" in paths


def test_list_files_language_filter():
    import json
    tree = [
        {"name": "main.py", "path": "main.py", "type": "file", "language": "python"},
        {"name": "app.ts", "path": "app.ts", "type": "file", "language": "typescript"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_data = Path(tmp) / proj_id
        proj_data.mkdir()
        (proj_data / "file_tree.json").write_text(json.dumps(tree))

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_data_dir = tmp
            results = list_files(proj_id, language="python")

    assert len(results) == 1
    assert results[0]["language"] == "python"


# ── Tool: run_tool dispatcher ─────────────────────────────────────────────────

def test_run_tool_unknown_tool():
    mock_chroma = MagicMock()
    result = run_tool("nonexistent_tool", {}, "proj", mock_chroma)
    assert result.error is not None
    assert "Unknown tool" in result.error


def test_run_tool_returns_tool_result():
    mock_chroma = MagicMock()
    with tempfile.TemporaryDirectory() as tmp:
        proj_id = "test-proj"
        proj_dir = Path(tmp) / proj_id
        proj_dir.mkdir()
        (proj_dir / "hello.py").write_text("print('hello')\n")

        with patch("app.agent.tools.settings") as mock_settings:
            mock_settings.projects_tmp_dir = tmp
            result = run_tool(
                "read_file",
                {"file_path": "hello.py"},
                proj_id,
                mock_chroma,
            )

    assert result.tool_name == "read_file"
    assert result.error is None
    assert result.duration_ms >= 0
    assert "hello" in str(result.output)
