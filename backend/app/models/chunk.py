from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Chunk(BaseModel):
    """Core chunk schema — every indexed unit of source code."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    file_path: str
    chunk_type: str  # function|class|method|import|config|fallback
    symbol_name: Optional[str] = None
    parent_class: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    language: str = "unknown"
    docstring: Optional[str] = None
    project_id: str

    @property
    def token_estimate(self) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(self.text) // 4

    def to_chroma_metadata(self) -> dict:
        """Flatten to ChromaDB-compatible metadata dict (no None values)."""
        return {
            k: v
            for k, v in {
                "file_path": self.file_path,
                "chunk_type": self.chunk_type,
                "symbol_name": self.symbol_name or "",
                "parent_class": self.parent_class or "",
                "start_line": self.start_line,
                "end_line": self.end_line,
                "language": self.language,
                "docstring": self.docstring or "",
                "project_id": self.project_id,
            }.items()
            if v is not None
        }


class ToolResult(BaseModel):
    """Structured output from any agent tool call."""

    tool_name: str
    tool_input: dict
    chunks: list[Chunk] = Field(default_factory=list)
    raw_output: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class Citation(BaseModel):
    """A source reference attached to a synthesized answer."""

    index: int
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    chunk_type: str = ""
