import logging
import sys
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


# ── JSON formatter (production) ───────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields passed via extra={...}
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ) and not key.startswith("_"):
                log_obj[key] = val
        return json.dumps(log_obj, default=str)


# ── Pretty formatter (dev mode) ───────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
MAGENTA = "\033[35m"
BLUE   = "\033[34m"
WHITE  = "\033[97m"

LEVEL_COLORS = {
    "DEBUG":    DIM + WHITE,
    "INFO":     GREEN,
    "WARNING":  YELLOW,
    "ERROR":    RED,
    "CRITICAL": BOLD + RED,
}


class PrettyFormatter(logging.Formatter):
    """Human-readable colored formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        level = record.levelname
        color = LEVEL_COLORS.get(level, WHITE)
        logger_short = record.name.split(".")[-1]

        # Base line
        line = (
            f"{DIM}{ts}{RESET} "
            f"{color}{level:<8}{RESET} "
            f"{CYAN}{logger_short}{RESET} "
            f"{record.getMessage()}"
        )

        # Append extra fields (skip internal ones)
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ) and not k.startswith("_")
        }
        if extras:
            extras_str = "  ".join(
                f"{DIM}{k}{RESET}={YELLOW}{json.dumps(v, default=str)}{RESET}"
                for k, v in extras.items()
            )
            line += f"\n          {extras_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


# ── LLM call logger ───────────────────────────────────────────────────────────

def log_llm_request(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    request_id: str | None = None,
) -> str:
    """Log an outgoing LLM request. Returns request_id for correlation."""
    rid = request_id or uuid.uuid4().hex[:8]
    logger = get_logger("llm")

    if settings.debug:
        # Pretty-print full prompt in debug mode
        _log_llm_request_pretty(rid, model, messages, tools)
    else:
        logger.info(
            "LLM request",
            extra={
                "request_id": rid,
                "model": model,
                "message_count": len(messages),
                "has_tools": bool(tools),
                "tool_names": [t["function"]["name"] for t in (tools or [])],
                "prompt_chars": sum(len(m.get("content") or "") for m in messages),
            },
        )
    return rid


def log_llm_response(
    request_id: str,
    model: str,
    content: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_ms: int = 0,
    finish_reason: str = "",
    tool_calls: list | None = None,
) -> None:
    """Log an LLM response."""
    logger = get_logger("llm")

    if settings.debug:
        _log_llm_response_pretty(
            request_id, model, content, input_tokens,
            output_tokens, duration_ms, finish_reason, tool_calls
        )
    else:
        logger.info(
            "LLM response",
            extra={
                "request_id": request_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "duration_ms": duration_ms,
                "finish_reason": finish_reason,
                "response_chars": len(content),
                "tool_calls": len(tool_calls or []),
            },
        )


def _log_llm_request_pretty(
    rid: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
) -> None:
    sep = "─" * 60
    lines = [
        f"{BOLD}{MAGENTA}┌─ LLM REQUEST {rid} ─ {model}{RESET}",
        f"{MAGENTA}│{RESET} {sep}",
    ]
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content") or ""
        role_color = {
            "system": CYAN, "user": GREEN,
            "assistant": YELLOW, "tool": MAGENTA,
        }.get(role, WHITE)
        lines.append(f"{MAGENTA}│{RESET} {role_color}{BOLD}[{role.upper()}]{RESET}")
        # Wrap long content
        for chunk in _wrap(content, 100):
            lines.append(f"{MAGENTA}│{RESET}   {DIM}{chunk}{RESET}")
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                lines.append(
                    f"{MAGENTA}│{RESET}   {YELLOW}⚙ tool_call: "
                    f"{fn.get('name')}({fn.get('arguments', '')[:120]}){RESET}"
                )
    if tools:
        lines.append(f"{MAGENTA}│{RESET} {sep}")
        lines.append(f"{MAGENTA}│{RESET} {CYAN}TOOLS: {', '.join(t['function']['name'] for t in tools)}{RESET}")
    lines.append(f"{MAGENTA}└{'─' * 62}{RESET}")
    print("\n".join(lines), flush=True)


def _log_llm_response_pretty(
    rid: str,
    model: str,
    content: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    finish_reason: str,
    tool_calls: list | None,
) -> None:
    sep = "─" * 60
    lines = [
        f"{BOLD}{BLUE}┌─ LLM RESPONSE {rid} ─ {model}{RESET}",
        f"{BLUE}│{RESET} {DIM}tokens: {input_tokens}in + {output_tokens}out  "
        f"latency: {duration_ms}ms  finish: {finish_reason}{RESET}",
        f"{BLUE}│{RESET} {sep}",
    ]
    if tool_calls:
        for tc in tool_calls:
            fn = tc.get("function", {})
            lines.append(
                f"{BLUE}│{RESET} {YELLOW}⚙ {fn.get('name')}({fn.get('arguments', '')[:200]}){RESET}"
            )
    if content:
        for chunk in _wrap(content, 100):
            lines.append(f"{BLUE}│{RESET}   {chunk}")
    lines.append(f"{BLUE}└{'─' * 62}{RESET}")
    print("\n".join(lines), flush=True)


def _wrap(text: str, width: int) -> list[str]:
    """Simple word-wrap for log output."""
    lines = []
    for raw_line in text.splitlines():
        if len(raw_line) <= width:
            lines.append(raw_line)
        else:
            while len(raw_line) > width:
                lines.append(raw_line[:width])
                raw_line = raw_line[width:]
            if raw_line:
                lines.append(raw_line)
    return lines or [""]


# ── Chunk / retrieval logger ──────────────────────────────────────────────────

def log_retrieval(
    project_id: str,
    query: str,
    semantic_count: int,
    bm25_count: int,
    fused_count: int,
    reranked_count: int,
    top_chunks: list[dict] | None = None,
) -> None:
    """Log retrieval pipeline results."""
    logger = get_logger("retrieval")
    logger.info(
        "Retrieval complete",
        extra={
            "project_id": project_id,
            "query_preview": query[:80],
            "semantic": semantic_count,
            "bm25": bm25_count,
            "fused": fused_count,
            "reranked": reranked_count,
        },
    )
    if settings.debug and top_chunks:
        logger = get_logger("retrieval")
        lines = [
            f"{BOLD}{GREEN}┌─ TOP CHUNKS (project={project_id}){RESET}",
            f"{GREEN}│{RESET} query: {DIM}{query[:100]}{RESET}",
        ]
        for i, c in enumerate(top_chunks[:5]):
            lines.append(
                f"{GREEN}│{RESET} {BOLD}#{i+1}{RESET} "
                f"{CYAN}{c.get('file_path', '?')}:{c.get('start_line', '?')}{RESET} "
                f"{YELLOW}{c.get('symbol_name') or c.get('chunk_type', '?')}{RESET} "
                f"score={c.get('score', 0):.3f}"
            )
            preview = (c.get('text') or '')[:120].replace('\n', ' ')
            lines.append(f"{GREEN}│{RESET}   {DIM}{preview}{RESET}")
        lines.append(f"{GREEN}└{'─' * 62}{RESET}")
        print("\n".join(lines), flush=True)


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure root logger. Uses pretty formatter in debug mode, JSON in prod."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if settings.debug:
        handler.setFormatter(PrettyFormatter())
    else:
        handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "chromadb", "sentence_transformers",
                  "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
