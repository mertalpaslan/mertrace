from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api.deps import get_session
from app.models.project import Project, ProjectCreate, ProjectRead
from app.core.logging import get_logger
from app.ingestion.pipeline import run_pipeline

logger = get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)):
    """List all indexed projects."""
    result = await session.exec(select(Project).order_by(Project.created_at.desc()))
    return result.all()


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Submit a GitHub URL or local path for indexing."""
    if not payload.url and not payload.local_path:
        raise HTTPException(400, "Provide either url or local_path")

    project = Project(
        name=payload.name,
        url=payload.url,
        local_path=payload.local_path,
        status="pending",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)

    background_tasks.add_task(run_pipeline, project.id)

    logger.info("Project created", extra={"project_id": project.id})
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get project status and manifest."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete project record and clean up files + ChromaDB collection."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    from app.api.deps import get_chroma
    from app.ingestion.embedder import delete_collection
    from app.ingestion.cloner import cleanup_project
    try:
        delete_collection(project_id, get_chroma())
    except Exception:
        pass
    try:
        cleanup_project(project_id)
    except Exception:
        pass

    await session.delete(project)
    await session.commit()
    logger.info("Project deleted", extra={"project_id": project_id})
