from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_TURNS = 20        # max turns kept in memory
MAX_TOKENS_APPROX = 4000  # rough char/3.5 budget for history


@dataclass
class Turn:
    role: str   # "user" | "assistant"
    content: str


@dataclass
class ConversationMemory:
    project_id: str
    turns: list[Turn] = field(default_factory=list)

    def add_user(self, content: str) -> None:
        self.turns.append(Turn(role="user", content=content))
        self._trim()

    def add_assistant(self, content: str) -> None:
        self.turns.append(Turn(role="assistant", content=content))
        self._trim()

    def to_messages(self, max_turns: int = 6) -> list[dict]:
        """Return last N turns as LiteLLM-compatible message dicts."""
        recent = self.turns[-max_turns * 2:] if max_turns else self.turns
        return [{"role": t.role, "content": t.content} for t in recent]

    def _trim(self) -> None:
        """Keep memory within turn and token limits."""
        # Trim by turn count
        if len(self.turns) > MAX_TURNS * 2:
            self.turns = self.turns[-(MAX_TURNS * 2):]
            # Always start with a user turn
            while self.turns and self.turns[0].role != "user":
                self.turns.pop(0)

        # Trim by approximate token budget
        while self._approx_tokens() > MAX_TOKENS_APPROX and len(self.turns) > 2:
            self.turns.pop(0)
            while self.turns and self.turns[0].role != "user":
                self.turns.pop(0)

    def _approx_tokens(self) -> int:
        total_chars = sum(len(t.content) for t in self.turns)
        return int(total_chars / 3.5)

    def clear(self) -> None:
        self.turns.clear()

    @property
    def turn_count(self) -> int:
        return len([t for t in self.turns if t.role == "user"])


# ── In-memory store: project_id -> ConversationMemory ─────────────────────────
# One memory per project (shared across all WS connections to same project)
_store: dict[str, ConversationMemory] = {}


def get_memory(project_id: str) -> ConversationMemory:
    if project_id not in _store:
        _store[project_id] = ConversationMemory(project_id=project_id)
    return _store[project_id]


def clear_memory(project_id: str) -> None:
    if project_id in _store:
        _store[project_id].clear()
        logger.info("Memory cleared", extra={"project_id": project_id})
