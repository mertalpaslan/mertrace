from __future__ import annotations

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])

_connections: dict[str, list[WebSocket]] = {}


def register_ws(project_id: str, ws: WebSocket) -> None:
    _connections.setdefault(project_id, []).append(ws)


def unregister_ws(project_id: str, ws: WebSocket) -> None:
    conns = _connections.get(project_id, [])
    if ws in conns:
        conns.remove(ws)


async def broadcast(project_id: str, event_type: str, payload: dict) -> None:
    msg = json.dumps({"type": event_type, **payload})
    dead = []
    for ws in _connections.get(project_id, []):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_ws(project_id, ws)


@router.websocket("/ws/{project_id}")
async def chat_websocket(websocket: WebSocket, project_id: str):
    await websocket.accept()
    register_ws(project_id, websocket)
    logger.info("WebSocket connected", extra={"project_id": project_id})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "invalid_json", "Message must be valid JSON")
                continue

            msg_type = message.get("type", "")

            if msg_type == "chat.message":
                mode = message.get("mode", "rag")
                if mode == "agent":
                    await _handle_agent(websocket, project_id, message)
                else:
                    await _handle_rag(websocket, project_id, message)
            elif msg_type == "memory.clear":
                from app.agent.memory import clear_memory
                clear_memory(project_id)
                await websocket.send_json({"type": "memory.cleared"})
            else:
                await _send_error(websocket, "unknown_type", f"Unknown type: {msg_type}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"project_id": project_id})
    finally:
        unregister_ws(project_id, websocket)


async def _handle_rag(websocket: WebSocket, project_id: str, message: dict) -> None:
    query = message.get("query", "").strip()
    history = message.get("history", [])
    language_filter = message.get("language_filter")
    file_filter = message.get("file_filter")

    if not query:
        await _send_error(websocket, "empty_query", "Query cannot be empty")
        return

    project = await _get_ready_project(project_id)
    if not project:
        await _send_error(websocket, "not_ready", "Project not found or not ready")
        return

    from app.api.deps import get_chroma
    from app.rag.retriever import retrieve
    from app.rag.reranker import rerank
    from app.rag.context_assembler import assemble
    from app.rag.synthesizer import synthesize_stream
    from app.core.config import settings

    try:
        chunks = retrieve(
            project_id=project_id,
            query=query,
            chroma_client=get_chroma(),
            top_k=settings.retrieval_top_k,
            language_filter=language_filter,
            file_filter=file_filter,
        )
        chunks = rerank(query=query, chunks=chunks, top_k=settings.rerank_top_k)
        context = assemble(query=query, chunks=chunks, max_tokens=settings.max_context_tokens)

        async for token in synthesize_stream(
            query=query,
            context=context,
            conversation_history=history,
        ):
            await websocket.send_json({"type": "chat.token", "token": token})

        await websocket.send_json({
            "type": "chat.done",
            "sources": [
                {
                    "index": c.index,
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "symbol_name": c.symbol_name,
                    "chunk_type": c.chunk_type,
                }
                for c in context.citations
            ],
            "context_tokens": context.estimated_tokens,
        })

    except Exception as e:
        logger.error("RAG error", extra={"error": str(e), "project_id": project_id})
        await _send_error(websocket, "rag_error", str(e))


async def _handle_agent(websocket: WebSocket, project_id: str, message: dict) -> None:
    query = message.get("query", "").strip()
    if not query:
        await _send_error(websocket, "empty_query", "Query cannot be empty")
        return

    project = await _get_ready_project(project_id)
    if not project:
        await _send_error(websocket, "not_ready", "Project not found or not ready")
        return

    from app.api.deps import get_chroma
    from app.agent.orchestrator import run_agent
    from app.agent.memory import get_memory

    memory = get_memory(project_id)
    chroma = get_chroma()

    async def emit(event_type: str, payload: dict) -> None:
        await websocket.send_json({"type": event_type, **payload})

    try:
        async for token in run_agent(
            query=query,
            project_id=project_id,
            chroma_client=chroma,
            memory=memory,
            emit=emit,
        ):
            await websocket.send_json({"type": "chat.token", "token": token})

        await websocket.send_json({
            "type": "chat.done",
            "sources": [],
            "context_tokens": 0,
        })

    except Exception as e:
        logger.error("Agent error", extra={"error": str(e), "project_id": project_id})
        await _send_error(websocket, "agent_error", str(e))


async def _get_ready_project(project_id: str):
    from app.api.deps import AsyncSessionLocal
    from app.models.project import Project
    async with AsyncSessionLocal() as session:
        project = await session.get(Project, project_id)
    if not project or project.status != "ready":
        return None
    return project


async def _send_error(ws: WebSocket, code: str, message: str) -> None:
    await ws.send_json({"type": "error", "code": code, "message": message})
