from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ProjectBase(SQLModel):
    name: str
    url: Optional[str] = None
    local_path: Optional[str] = None


class Project(ProjectBase, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=_uuid, primary_key=True)
    status: str = Field(default="pending")
    # pending | cloning | walking | chunking | embedding | umap | ready | error

    error_message: Optional[str] = None
    chunk_count: int = Field(default=0)
    file_count: int = Field(default=0)
    languages: Optional[str] = None  # JSON-encoded list
    index_duration_ms: Optional[int] = None
    umap_ready: bool = Field(default=False)

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: str
    status: str
    error_message: Optional[str]
    chunk_count: int
    file_count: int
    languages: Optional[str]
    umap_ready: bool
    created_at: datetime
    updated_at: datetime


class ProjectStatusUpdate(SQLModel):
    status: str
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
    file_count: Optional[int] = None
    languages: Optional[str] = None
    index_duration_ms: Optional[int] = None
    umap_ready: Optional[bool] = None
