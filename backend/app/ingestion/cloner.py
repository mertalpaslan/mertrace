import shutil
import time
from pathlib import Path
from dataclasses import dataclass

import git

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CLONE_TIMEOUT_S = 120


@dataclass
class CloneResult:
    project_dir: Path
    is_local: bool
    duration_ms: int


def clone_repo(project_id: str, url: str) -> CloneResult:
    """
    Shallow-clone a GitHub URL into the project tmp directory.
    Falls back to full clone if shallow fails.
    """
    dest = Path(settings.projects_tmp_dir) / project_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    try:
        logger.info("Cloning repo (shallow)", extra={"url": url, "dest": str(dest)})
        git.Repo.clone_from(
            url,
            dest,
            depth=1,
            single_branch=True,
            kill_after_timeout=CLONE_TIMEOUT_S,
        )
    except git.GitCommandError as e:
        logger.warning(
            "Shallow clone failed, retrying full clone",
            extra={"url": url, "error": str(e)},
        )
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        git.Repo.clone_from(url, dest, kill_after_timeout=CLONE_TIMEOUT_S)

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info("Clone complete", extra={"dest": str(dest), "duration_ms": duration_ms})
    return CloneResult(project_dir=dest, is_local=False, duration_ms=duration_ms)


def copy_local(project_id: str, local_path: str) -> CloneResult:
    """Copy a local directory into the project tmp directory."""
    src = Path(local_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Local path does not exist: {src}")

    dest = Path(settings.projects_tmp_dir) / project_id
    if dest.exists():
        shutil.rmtree(dest)

    t0 = time.monotonic()
    shutil.copytree(src, dest, symlinks=False, ignore=_ignore_patterns())
    duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "Local copy complete",
        extra={"src": str(src), "dest": str(dest), "duration_ms": duration_ms},
    )
    return CloneResult(project_dir=dest, is_local=True, duration_ms=duration_ms)


def cleanup_project(project_id: str) -> None:
    """Remove cloned files for a project."""
    dest = Path(settings.projects_tmp_dir) / project_id
    if dest.exists():
        shutil.rmtree(dest)
        logger.info("Cleaned up project dir", extra={"project_id": project_id})


def _ignore_patterns():
    """Directories to skip during local copy."""
    return shutil.ignore_patterns(
        ".git",
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
        "node_modules",
        ".next",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
        "*.egg-info",
    )
