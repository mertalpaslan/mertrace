import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from pathlib import Path

from app.api.deps import get_session
from app.models.project import Project
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["files"])


@router.get("/{project_id}/tree")
async def get_file_tree(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return the nested file tree for a ready project."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.status != "ready":
        raise HTTPException(400, f"Project not ready (status: {project.status})")

    tree_file = Path(settings.projects_data_dir) / project_id / "file_tree.json"
    if not tree_file.exists():
        raise HTTPException(404, "File tree not yet generated")

    return {"tree": json.loads(tree_file.read_text()), "project_id": project_id}


@router.get("/{project_id}/file", response_class=PlainTextResponse)
async def get_file_content(
    project_id: str,
    path: str = Query(..., description="Relative file path within the project"),
    session: AsyncSession = Depends(get_session),
):
    """Return raw file content. Sandboxed to project tmp directory."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    base = (Path(settings.projects_tmp_dir) / project_id).resolve()
    target = (base / path).resolve()

    if not str(target).startswith(str(base)):
        raise HTTPException(403, "Access denied")
    if not target.exists():
        raise HTTPException(404, "File not found")
    if not target.is_file():
        raise HTTPException(400, "Path is not a file")

    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error("File read error", extra={"path": str(target), "error": str(e)})
        raise HTTPException(500, "Could not read file")


@router.get("/{project_id}/embeddings")
async def get_embeddings(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return 2D UMAP coordinates and cluster labels for scatter plot."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.umap_ready:
        raise HTTPException(400, "UMAP not yet computed for this project")

    umap_file = Path(settings.projects_data_dir) / project_id / "umap_coords.json"
    if not umap_file.exists():
        raise HTTPException(404, "UMAP data file not found")

    return json.loads(umap_file.read_text())
