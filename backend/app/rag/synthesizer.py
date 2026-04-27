from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Optional

from litellm import acompletion

from app.rag.context_assembler import AssembledContext
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert code assistant analyzing a software project.
You answer questions about the codebase using ONLY the provided code context.
Be precise, cite specific files and line numbers, and explain code clearly.
If the context does not contain enough information to answer, say so honestly.
Do not hallucinate code that is not in the context."""


async def synthesize_stream(
    query: str,
    context: AssembledContext,
    model: Optional[str] = None,
    conversation_history: Optional[list[dict]] = None,
) -> AsyncGenerator[str, None]:
    """
    Single-pass LLM call with streaming.
    Yields token strings as they arrive.
    """
    model = model or settings.litellm_model
    messages = _build_messages(query, context, conversation_history)

    t0 = time.monotonic()
    total_tokens = 0

    try:
        response = await acompletion(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.2,
            max_tokens=2048,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
                total_tokens += 1

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Synthesis complete",
            extra={
                "model": model,
                "tokens_approx": total_tokens,
                "context_tokens": context.estimated_tokens,
                "duration_ms": duration_ms,
            },
        )

    except Exception as e:
        logger.error("LLM synthesis failed", extra={"error": str(e), "model": model})
        yield f"\n\n[Error: {str(e)}]"


def _build_messages(
    query: str,
    context: AssembledContext,
    history: Optional[list[dict]],
) -> list[dict]:
    """Build the message list for the LLM call."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject conversation history (last 6 turns max to stay within budget)
    if history:
        messages.extend(history[-6:])

    user_content = (
        f"## Code Context\n\n{context.context_text}\n\n"
        f"## Question\n\n{query}"
    )
    messages.append({"role": "user", "content": user_content})
    return messages
