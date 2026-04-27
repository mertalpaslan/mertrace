from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Callable

from litellm import acompletion

from app.agent.tools import TOOL_SCHEMAS, run_tool, ToolResult
from app.agent.memory import ConversationMemory
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert code assistant with access to tools for exploring a software project.
Use tools to gather precise information before answering.
Always cite specific files and line numbers in your final answer.
Be concise and technical. Do not guess — use tools to verify."""

MAX_TOOL_ROUNDS = 3  # max tool call rounds per query


async def run_agent(
    query: str,
    project_id: str,
    chroma_client,
    memory: ConversationMemory,
    emit: Callable[[str, dict], None],
) -> AsyncGenerator[str, None]:
    """
    3-step linear agent:
      1. LLM decides which tools to call
      2. Execute tools, collect results
      3. Single-pass LLM synthesis with tool results

    Streams tokens via async generator.
    Emits agent.tool_start / agent.tool_done events via emit().
    """
    import chromadb as _chromadb

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *memory.to_messages(max_turns=6),
        {"role": "user", "content": query},
    ]

    tool_results: list[ToolResult] = []

    # ── Step 1 & 2: Tool calling rounds ──────────────────────────────────────
    for round_num in range(MAX_TOOL_ROUNDS):
        response = await acompletion(
            model=settings.litellm_model,
            messages=messages,
            tools=_build_tool_specs(),
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1024,
            stream=False,
        )

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            # No more tools needed — proceed to synthesis
            break

        # Add assistant message with tool calls to context
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [
                             {
                                 "id": tc.id,
                                 "type": "function",
                                 "function": {
                                     "name": tc.function.name,
                                     "arguments": tc.function.arguments,
                                 },
                             }
                             for tc in tool_calls
                         ]})

        # Execute each tool call
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                tool_input = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_input = {}

            # Emit tool start event
            await emit("agent.tool_start", {
                "tool_name": tool_name,
                "tool_input": tool_input,
            })

            # Run tool in executor (may do file I/O)
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, run_tool, tool_name, tool_input, project_id, chroma_client
            )
            tool_results.append(result)

            # Emit tool done event
            await emit("agent.tool_done", result.to_ws_payload())

            # Add tool result to messages
            output_str = json.dumps(result.output) if not isinstance(result.output, str) \
                else result.output
            if result.error:
                output_str = f"Error: {result.error}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output_str[:4000],  # cap tool output
            })

        logger.debug(
            "Tool round complete",
            extra={"round": round_num + 1, "tools_called": len(tool_calls)},
        )

    # ── Step 3: Final synthesis with streaming ────────────────────────────────
    # Add synthesis instruction
    messages.append({
        "role": "user",
        "content": (
            "Based on the tool results above, provide a clear and complete answer. "
            "Cite specific files and line numbers."
        ) if tool_results else query,
    })

    stream_response = await acompletion(
        model=settings.litellm_model,
        messages=messages,
        stream=True,
        temperature=0.2,
        max_tokens=2048,
    )

    full_response = ""
    async for chunk in stream_response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            full_response += delta.content
            yield delta.content

    # Store in memory
    memory.add_user(query)
    memory.add_assistant(full_response)

    logger.info(
        "Agent run complete",
        extra={
            "project_id": project_id,
            "tool_rounds": len(tool_results),
            "response_len": len(full_response),
        },
    )


def _build_tool_specs() -> list[dict]:
    """Convert TOOL_SCHEMAS to LiteLLM tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_SCHEMAS
    ]
