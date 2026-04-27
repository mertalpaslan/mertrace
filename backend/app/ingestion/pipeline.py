from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.project import Project
from app.ingestion.cloner import clone_repo, copy_local
from app.ingestion.walker import walk_project
from app.ingestion.chunker import chunk_file
from app.ingestion.embedder import embed_chunks, delete_collection
from app.ingestion.umap_builder import build_umap
from app.api.deps import get_chroma, AsyncSessionLocal
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PipelineError(Exception):
    pass


async def run_pipeline(project_id: str) -> None:
    """
    Full ingestion pipeline for a project.
    Stages: clone -> walk -> chunk -> embed -> umap
    Streams progress via WebSocket broadcast.
    """
    # Import here to avoid circular import at module load
    from app.api.routes.chat import broadcast

    async def emit(event_type: str, payload: dict) -> None:
        await broadcast(project_id, event_type, payload)

    async with AsyncSessionLocal() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise PipelineError(f"Project {project_id} not found")

        try:
            # ── Stage 1: Clone / Copy ─────────────────────────────────────────
            await _update_status(session, project, "cloning")
            await emit("index.progress", {"stage": "cloning", "pct": 5})

            loop = asyncio.get_event_loop()
            if project.url:
                clone_result = await loop.run_in_executor(
                    None, clone_repo, project_id, project.url
                )
            elif project.local_path:
                clone_result = await loop.run_in_executor(
                    None, copy_local, project_id, project.local_path
                )
            else:
                raise PipelineError("Project has neither url nor local_path")

            # ── Stage 2: Walk ─────────────────────────────────────────────────
            await _update_status(session, project, "walking")
            await emit("index.progress", {"stage": "walking", "pct": 20})

            entries, tree = await loop.run_in_executor(
                None, walk_project, clone_result.project_dir
            )

            tree_dir = Path(settings.projects_data_dir) / project_id
            tree_dir.mkdir(parents=True, exist_ok=True)
            (tree_dir / "file_tree.json").write_text(json.dumps(tree))

            file_count = len(entries)
            languages = list({e.language for e in entries if e.language != "unknown"})

            # ── Stage 3: Chunk ────────────────────────────────────────────────
            await _update_status(session, project, "chunking")
            await emit("index.progress", {"stage": "chunking", "pct": 35})

            all_chunks = []
            for entry in entries:
                chunks = await loop.run_in_executor(None, chunk_file, entry, project_id)
                all_chunks.extend(chunks)

            logger.info(
                "Chunking complete",
                extra={"project_id": project_id, "chunk_count": len(all_chunks)},
            )

            # ── Stage 4: Embed ────────────────────────────────────────────────
            await _update_status(session, project, "embedding")
            await emit("index.progress", {"stage": "embedding", "pct": 50})

            chroma = get_chroma()

            def _sync_progress(done: int, total: int) -> None:
                pct = 50 + int((done / total) * 30)
                asyncio.run_coroutine_threadsafe(
                    emit("index.progress", {"stage": "embedding", "pct": pct,
                                            "done": done, "total": total}),
                    loop,
                )

            await loop.run_in_executor(
                None, embed_chunks, all_chunks, chroma, _sync_progress
            )

            # ── Stage 5: UMAP ─────────────────────────────────────────────────
            await _update_status(session, project, "umap")
            await emit("index.progress", {"stage": "umap", "pct": 82})

            await loop.run_in_executor(None, build_umap, project_id, chroma)

            # ── Done ──────────────────────────────────────────────────────────
            project.status = "ready"
            project.chunk_count = len(all_chunks)
            project.file_count = file_count
            project.languages = json.dumps(languages)
            project.umap_ready = True
            session.add(project)
            await session.commit()

            await emit("index.progress", {"stage": "ready", "pct": 100})
            await emit("index.done", {
                "chunk_count": len(all_chunks),
                "file_count": file_count,
                "languages": languages,
            })
            logger.info("Pipeline complete", extra={"project_id": project_id})

        except Exception as e:
            logger.error(
                "Pipeline failed",
                extra={"project_id": project_id, "error": str(e)},
            )
            project.status = "error"
            project.error_message = str(e)[:500]
            session.add(project)
            await session.commit()
            await emit("index.error", {"message": str(e)})
            raise


async def _update_status(session: AsyncSession, project: Project, status: str) -> None:
    project.status = status
    session.add(project)
    await session.commit()
    logger.info("Pipeline stage", extra={"project_id": project.id, "status": status})
