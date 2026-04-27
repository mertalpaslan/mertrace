import os
from pathlib import Path
from typing import Optional

import pathspec
import chardet

from app.core.logging import get_logger

logger = get_logger(__name__)

# Max file size to index (skip binaries / huge generated files)
MAX_FILE_BYTES = 512 * 1024  # 512 KB

LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".md": "markdown",
    ".toml": "config",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
    ".env": "config",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".dockerfile": "config",
    ".tf": "config",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "css",
}

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".next", "dist", "build", ".pytest_cache", ".ruff_cache",
    "*.egg-info", ".mypy_cache", ".tox", "coverage",
}


class FileEntry:
    __slots__ = ("rel_path", "abs_path", "language", "size_bytes")

    def __init__(self, rel_path: str, abs_path: Path, language: str, size_bytes: int):
        self.rel_path = rel_path
        self.abs_path = abs_path
        self.language = language
        self.size_bytes = size_bytes

    def read_text(self) -> Optional[str]:
        """Read file content, detecting encoding. Returns None if binary."""
        try:
            raw = self.abs_path.read_bytes()
            detected = chardet.detect(raw[:4096])
            encoding = detected.get("encoding") or "utf-8"
            return raw.decode(encoding, errors="replace")
        except Exception as e:
            logger.warning("Could not read file", extra={"path": self.rel_path, "error": str(e)})
            return None

    def to_tree_node(self) -> dict:
        return {
            "name": Path(self.rel_path).name,
            "path": self.rel_path,
            "type": "file",
            "language": self.language,
        }


def walk_project(project_dir: Path) -> tuple[list[FileEntry], list[dict]]:
    """
    Walk a project directory and return:
    - flat list of FileEntry objects (for chunking)
    - nested tree structure (for frontend FileExplorer)
    """
    gitignore_spec = _load_gitignore(project_dir)
    entries: list[FileEntry] = []
    tree_root: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(project_dir):
        # Prune skip dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        rel_dir = Path(dirpath).relative_to(project_dir)

        for filename in sorted(filenames):
            abs_path = Path(dirpath) / filename
            rel_path = str(rel_dir / filename)

            # Skip gitignored files
            if gitignore_spec and gitignore_spec.match_file(rel_path):
                continue

            size = abs_path.stat().st_size
            if size > MAX_FILE_BYTES:
                logger.debug("Skipping large file", extra={"path": rel_path, "size": size})
                continue

            ext = abs_path.suffix.lower()
            # Skip Dockerfile (no extension) by name
            if filename.lower() == "dockerfile":
                ext = ".dockerfile"

            language = LANG_MAP.get(ext, "unknown")
            if language == "unknown" and not _is_text_file(abs_path):
                continue

            entry = FileEntry(
                rel_path=rel_path,
                abs_path=abs_path,
                language=language,
                size_bytes=size,
            )
            entries.append(entry)

    tree_root = _build_tree(entries)
    logger.info(
        "Walk complete",
        extra={"file_count": len(entries), "project_dir": str(project_dir)},
    )
    return entries, tree_root


def _load_gitignore(project_dir: Path) -> Optional[pathspec.PathSpec]:
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        return None
    try:
        patterns = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitignore", patterns)
    except Exception:
        return None


def _is_text_file(path: Path) -> bool:
    """Quick binary check: read first 512 bytes and look for null bytes."""
    try:
        chunk = path.read_bytes()[:512]
        return b"\x00" not in chunk
    except Exception:
        return False


def _build_tree(entries: list[FileEntry]) -> list[dict]:
    """Build a nested directory tree from flat file entries."""
    root: dict = {"children": {}}

    for entry in entries:
        parts = Path(entry.rel_path).parts
        node = root
        for part in parts[:-1]:
            if part not in node["children"]:
                node["children"][part] = {
                    "name": part,
                    "path": part,
                    "type": "directory",
                    "children": {},
                }
            node = node["children"][part]
        node["children"][parts[-1]] = entry.to_tree_node()

    return _dict_to_list(root["children"])


def _dict_to_list(children: dict) -> list[dict]:
    result = []
    for node in children.values():
        if node["type"] == "directory":
            node["children"] = _dict_to_list(node["children"])
        result.append(node)
    # Directories first, then files, both alphabetical
    result.sort(key=lambda n: (0 if n["type"] == "directory" else 1, n["name"]))
    return result
