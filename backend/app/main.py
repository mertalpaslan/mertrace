from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.deps import init_db
from app.api.routes import projects, files, chat

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info(
        "Starting Codebase Analyzer",
        extra={"version": settings.version, "debug": settings.debug},
    )
    await init_db()
    yield
    logger.info("Shutting down Codebase Analyzer")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-Powered Codebase Analyzer — Portfolio Project",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(projects.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(chat.router)


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.version,
        "app": settings.app_name,
    }
