# PROJECT_MAP.md
# AI-Powered Codebase Analyzer — Implementation Roadmap

> **Portfolio Project** | Read `CONTEXT.md` before every session. Read `SYSTEM_DESIGN.md` before implementing any component.

---

## Ground Rules

1. **Phases are sequential** — never start Phase N+1 until Phase N acceptance criteria pass.
2. **No file exceeds 400 lines** — plan the module split before writing.
3. **Agent = 3 steps, not a loop** — Search → Assemble → Synthesize. One LLM call per query.
4. **All heavy work is local** — embedding, chunking, reranking, UMAP never touch the LLM.
5. **Update `CONTEXT.md`** at the end of every session — it is the project's memory.

---

## Overview

Six phases, each with atomic tasks, implementation notes, and hard acceptance criteria.
Estimated total: **15–20 focused coding sessions**.

---

## Phase 1 — Project Scaffold & Dev Environment

**Goal:** A running skeleton — no features, but an unbreakable foundation.

### Directory Layout

```
codebase-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── projects.py   # CRUD + indexing trigger
│   │   │   │   ├── chat.py       # WebSocket endpoint
│   │   │   │   └── files.py      # File tree + raw content
│   │   │   └── deps.py           # FastAPI dependency injection
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings, env vars
│   │   │   └── logging.py        # structured JSON logging
│   │   ├── ingestion/
│   │   │   ├── cloner.py         # GitPython clone logic
│   │   │   ├── walker.py         # pathspec file walker
│   │   │   ├── chunker.py        # tree-sitter AST chunker
│   │   │   ├── chunker_fallback.py # sliding window fallback
│   │   │   └── embedder.py       # ChromaDB batch embedder
│   │   ├── rag/
│   │   │   ├── retriever.py      # dense + BM25 + RRF fusion
│   │   │   ├── reranker.py       # FlashRank cross-encoder
│   │   │   └── assembler.py      # token budget + citations
│   │   ├── agent/
│   │   │   ├── orchestrator.py   # 3-step Search→Assemble→Synth
│   │   │   ├── tools.py          # all local tool implementations
│   │   │   └── memory.py         # conversation turn history
│   │   ├── models/
│   │   │   ├── project.py        # SQLModel Project table
│   │   │   └── chunk.py          # Pydantic Chunk schema
│   │   └── main.py               # FastAPI app + lifespan
│   ├── tests/
│   │   ├── test_chunker.py
│   │   ├── test_retriever.py
│   │   └── test_api.py
│   ├── pyproject.toml
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileExplorer/     # left pane
│   │   │   ├── VectorViz/        # middle pane — scatter + preview
│   │   │   └── ChatPanel/        # right pane
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts   # WS with exponential backoff
│   │   │   └── useProject.ts     # TanStack Query wrappers
│   │   ├── store/
│   │   │   └── appStore.ts       # Zustand global state
│   │   ├── api/
│   │   │   └── client.ts         # typed fetch wrappers
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── chroma/                   # ChromaDB persistent storage
│   └── projects/                 # umap_coords.json per project
├── logs/
│   └── llm_usage.jsonl           # token + cost log per query
├── Makefile
├── docker-compose.yml
└── README.md
```

### Tasks

- [ ] 1.1 Create full directory structure above
- [ ] 1.2 Init Python env with `uv` — create `pyproject.toml`
- [ ] 1.3 Create `backend/app/main.py` — FastAPI app with lifespan, CORS, routers
- [ ] 1.4 Create `backend/app/core/config.py` — pydantic-settings with all env vars
- [ ] 1.5 Create `backend/app/core/logging.py` — structured JSON logging
- [ ] 1.6 Create `backend/app/models/project.py` — SQLModel Project + init DB
- [ ] 1.7 Create `backend/app/models/chunk.py` — Pydantic Chunk schema
- [ ] 1.8 Scaffold all route files with placeholder `NotImplemented` responses
- [ ] 1.9 Init ChromaDB client in `deps.py` (persistent, `./data/chroma/`)
- [ ] 1.10 Create frontend with `npm create vite@latest` (React + TypeScript)
- [ ] 1.11 Install frontend deps: Tailwind, shadcn/ui, Zustand, TanStack Query
- [ ] 1.12 Build blank 3-pane layout in `App.tsx` with placeholder panels
- [ ] 1.13 Create `Makefile` — `make dev`, `make install`, `make test`, `make lint`
- [ ] 1.14 Create `.env.example` with all required variables
- [ ] 1.15 Write first passing test: `GET /api/health` returns 200

### .env.example Variables

```
LITELLM_MODEL=claude-haiku-3-5
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
CHROMA_PERSIST_DIR=./data/chroma
PROJECTS_TMP_DIR=/tmp/codebase_analyzer
MAX_CONTEXT_TOKENS=4000
LOG_LEVEL=INFO
```

### Acceptance Criteria

- [ ] `make dev` starts backend (`:8000`) and frontend (`:5173`) concurrently
- [ ] `GET /api/health` → `{ "status": "ok", "version": "0.1.0" }`
- [ ] Frontend renders 3-pane layout — left/middle/right visible with placeholder text
- [ ] `make test` runs and passes the health check test
- [ ] `make lint` runs `ruff check` with zero errors

---

## Phase 2 — Repository Ingestion Pipeline

**Goal:** Clone a repo, walk its files, chunk them with AST precision, embed locally, and store in ChromaDB. No LLM calls in this phase.

### Tasks

**Cloning & Walking**
- [ ] 2.1 `cloner.py` — GitPython shallow clone (`--depth=1`), progress callback via generator
- [ ] 2.2 `cloner.py` — fallback to full clone if shallow fails; support `GITHUB_TOKEN` for private repos
- [ ] 2.3 `walker.py` — `pathspec` `.gitignore`-aware walker; skip binaries, lock files, build dirs
- [ ] 2.4 `walker.py` — language detection via extension map + `chardet` encoding check

**AST Chunking**
- [ ] 2.5 `chunker.py` — tree-sitter parser for Python, JS, TS, Go (via `tree-sitter-languages`)
- [ ] 2.6 `chunker.py` — extract: `function_definition`, `class_definition`, `import_statement`, `decorated_definition`
- [ ] 2.7 `chunker.py` — oversized node handler: sliding window with 20% overlap, `tiktoken` for counting
- [ ] 2.8 `chunker_fallback.py` — sliding window chunker for unsupported languages
- [ ] 2.9 Write unit tests for each chunk type (function, class, import, fallback)

**Embedding & Storage**
- [ ] 2.10 `embedder.py` — batch embed with `sentence-transformers` (`all-MiniLM-L6-v2`)
- [ ] 2.11 `embedder.py` — store chunks + metadata in ChromaDB (one collection per project UUID)
- [ ] 2.12 `embedder.py` — write project manifest JSON: `{ file_count, chunk_count, languages, timestamp }`
- [ ] 2.13 UMAP + HDBSCAN post-processing — compute 2D coords, save to `data/projects/{id}/umap_coords.json`

**API & Streaming**
- [ ] 2.14 `POST /api/projects` — accept `{ url, name }`, trigger async indexing task, return `project_id`
- [ ] 2.15 `GET /api/projects/{id}` — return status, manifest, language breakdown
- [ ] 2.16 `GET /api/projects` — list all projects from SQLite
- [ ] 2.17 WebSocket `index.progress` events — stream `{ stage, percent, current_file, chunks_so_far }`
- [ ] 2.18 WebSocket `index.done` event — stream `{ project_id, chunk_count, duration_ms }`

### AST Chunking Logic

```
for each file in walker output:
  1. Detect language from extension map
  2. If supported: parse with tree-sitter → AST root node
  3. Walk AST, collect target node types:
       function_definition  → full body text + signature
       class_definition     → signature + docstring only (not methods)
       method_definition    → full body (tagged with parent_class)
       import_statement     → accumulate all into ONE import chunk
       decorated_definition → include decorator lines in chunk text
  4. For any node where tiktoken count > MAX_TOKENS (512):
       apply sliding window with 20% overlap
  5. Attach metadata to every chunk (see Chunk schema)
  6. If language unsupported: route to chunker_fallback.py
  7. Return List[Chunk]
```

### Chunk Schema

```python
class Chunk(BaseModel):
    id: str                  # uuid4
    text: str                # raw source text of the chunk
    file_path: str           # relative to project root
    chunk_type: str          # function|class|method|import|config|fallback
    symbol_name: str | None  # function/class name if applicable
    parent_class: str | None # for methods
    start_line: int
    end_line: int
    language: str
    docstring: str | None
    project_id: str
```

### Supported Languages

| Language | Extensions | Parser |
|---|---|---|
| Python | `.py` | tree-sitter-python |
| JavaScript | `.js`, `.jsx` | tree-sitter-javascript |
| TypeScript | `.ts`, `.tsx` | tree-sitter-typescript |
| Go | `.go` | tree-sitter-go |
| Markdown | `.md` | paragraph boundary splitter |
| Other | `*` | `chunker_fallback.py` sliding window |

### Acceptance Criteria

- [ ] Indexing the FastAPI repo (~500 files) completes in under 90 seconds
- [ ] Every chunk contains all fields from the Chunk schema above
- [ ] ChromaDB collection is queryable immediately after `index.done` fires
- [ ] `umap_coords.json` exists and contains `{ points: [{x, y, chunk_id, chunk_type, file_path}], clusters: [...] }`
- [ ] Progress WebSocket events fire for every stage: `cloning → walking → chunking → embedding → umap`
- [ ] Unit tests pass for: Python function chunk, Python class chunk, TS function chunk, fallback chunk

---

## Phase 3 — Search-First RAG Chat

**Goal:** Users can ask questions and receive streamed, cited answers. The 3-step pipeline (Search → Assemble → Synthesize) is fully implemented here. **One LLM call per query — enforced.**

### Tasks

**Step 1 — Search (local)**
- [ ] 3.1 `retriever.py` — ChromaDB dense search, `top_k=20`, returns `List[Chunk]`
- [ ] 3.2 `retriever.py` — BM25 index built from all chunk texts at query time (`rank-bm25`)
- [ ] 3.3 `retriever.py` — Reciprocal Rank Fusion merges dense + sparse → unified top-20
- [ ] 3.4 `retriever.py` — HyDE fallback: if RRF returns 0 results, generate hypothetical answer, re-embed, retry once

**Step 2 — Assemble (local)**
- [ ] 3.5 `reranker.py` — FlashRank cross-encoder reranks top-20 → top-5
- [ ] 3.6 `assembler.py` — deduplicate overlapping chunks (same file + overlapping lines)
- [ ] 3.7 `assembler.py` — `tiktoken` token budget enforcer: hard cap at `MAX_CONTEXT_TOKENS` (4,000)
- [ ] 3.8 `assembler.py` — build citation map: `{ citation_id → { file_path, start_line, symbol_name } }`
- [ ] 3.9 `assembler.py` — format final context string with citation markers `[1]`, `[2]`...

**Step 3 — Synthesize (1 LLM call)**
- [ ] 3.10 `orchestrator.py` — LiteLLM call with assembled context + system prompt
- [ ] 3.11 `orchestrator.py` — stream response tokens via WebSocket `chat.token` events
- [ ] 3.12 `orchestrator.py` — on stream end, emit `chat.done` with sources + token count + cost
- [ ] 3.13 `orchestrator.py` — log every LLM call to `logs/llm_usage.jsonl`

**WebSocket & API**
- [ ] 3.14 `chat.py` route — WebSocket `/ws/{project_id}`, handle `chat.message` events
- [ ] 3.15 `chat.py` route — validate `mode` field: `"rag"` routes to RAG orchestrator

**Frontend**
- [ ] 3.16 `ChatPanel` component — message list with streaming token renderer
- [ ] 3.17 `ChatPanel` — citation chips rendered inline (e.g. `[auth.py:42]`)
- [ ] 3.18 Citation chip click → emit event to middle pane to open file at line
- [ ] 3.19 `useWebSocket.ts` hook — connect, send, receive, exponential backoff reconnect

### System Prompt

```
You are an expert code analyst for the repository: {repo_name}.
Answer the user's question using ONLY the context chunks provided below.
For every claim, cite the source using its [N] marker.
If the context is insufficient, say exactly: "I could not find enough context to answer this."
Do not hallucinate file names, function names, or line numbers.

Context:
{assembled_context}
```

### Acceptance Criteria

- [ ] First token streams to UI within 3 seconds of sending a query
- [ ] Every response includes at least one `[N]` citation
- [ ] `chat.done` payload contains `total_tokens` and `cost_usd`
- [ ] `logs/llm_usage.jsonl` has a new entry after every query
- [ ] HyDE fallback fires only when Step 1 returns zero results (verify with test)
- [ ] Clicking a citation chip opens the correct file at the correct line in middle pane

---

## Phase 4 — Frontend Polish & Vector Visualization

**Goal:** Build the complete 3-pane UI. The UMAP scatter plot is the portfolio's visual centrepiece — it must be interactive, fast, and connected to the chat.

### Tasks

**Left Pane — File Explorer**
- [ ] 4.1 `FileExplorer` component — fetch `/api/projects/{id}/tree`, render collapsible tree
- [ ] 4.2 Language badge per file (colour-coded dot: Python=blue, TS=cyan, Go=teal)
- [ ] 4.3 Active file highlight — syncs with middle pane preview and chat citations
- [ ] 4.4 Search/filter input — filters visible files by name in real time

**Middle Pane — Map Mode (UMAP Scatter)**
- [ ] 4.5 `VectorViz` component — fetch `/api/projects/{id}/embeddings`, render with Observable Plot
- [ ] 4.6 Canvas renderer for 10k+ points (Observable Plot `dot()` mark, no SVG)
- [ ] 4.7 Colour toggle: by `chunk_type` / `language` / `cluster` (Zustand state)
- [ ] 4.8 Hover tooltip: symbol name, file path, chunk type
- [ ] 4.9 Click point → open file in Preview Mode + highlight in File Explorer
- [ ] 4.10 Chat retrieval pulse: when `chat.done` fires, animate retrieved chunk points
- [ ] 4.11 Cluster label overlays — centroid labels from HDBSCAN cluster names

**Middle Pane — Preview Mode (File Viewer)**
- [ ] 4.12 `FilePreview` component — fetch `/api/projects/{id}/file?path=`, render with Shiki
- [ ] 4.13 Line highlight — scroll to and highlight `start_line`–`end_line` from citation
- [ ] 4.14 Tab bar — switch between Map Mode and Preview Mode

**Project Submission & Progress**
- [ ] 4.15 `ProjectSubmitForm` — URL input + optional name field, POST to `/api/projects`
- [ ] 4.16 `IndexingProgress` component — stage labels + animated progress bar from WebSocket
- [ ] 4.17 Project history sidebar — list from `GET /api/projects`, click to switch active project

**Global UI**
- [ ] 4.18 Dark mode default (Tailwind `dark:` classes, `class="dark"` on `<html>`)
- [ ] 4.19 Responsive layout — minimum 1280px, panels resizable via drag handle
- [ ] 4.20 Token usage badge in chat header — shows `total_tokens` and `~$cost` from last query

### Acceptance Criteria

- [ ] File tree renders correctly for repos with 1,000+ files without lag
- [ ] UMAP scatter renders 10,000+ points at 60fps (canvas, not SVG)
- [ ] Clicking a citation chip: file opens in Preview Mode at correct line AND point pulses in scatter
- [ ] Indexing progress bar advances through all 5 stages with correct labels
- [ ] Dark mode is default; no white flash on load
- [ ] UI is usable at exactly 1280px width

---

## Phase 5 — Agentic Workflow

**Goal:** Upgrade the chat from single-shot RAG to a structured agent that uses multiple local tools before making its single LLM call. The agent's tool execution trace is fully visible in the UI — this is the portfolio's most impressive demo feature.

> **Architecture reminder:** The agent is NOT a ReAct loop. It is the same 3-step pipeline as RAG, but Step 1 executes multiple local tools in sequence before assembling context. The LLM is still called exactly once.

### Tasks

**Backend — Tools**
- [ ] 5.1 `tools.py` — `search_codebase(query)` → hybrid retriever (reuses Phase 3 retriever)
- [ ] 5.2 `tools.py` — `find_symbol(name)` → ChromaDB metadata filter on `symbol_name`
- [ ] 5.3 `tools.py` — `read_file(path)` → sandboxed file read, returns text + line count
- [ ] 5.4 `tools.py` — `list_directory(path)` → walker output filtered to given dir
- [ ] 5.5 `tools.py` — `grep_codebase(pattern)` → regex search over all chunk texts
- [ ] 5.6 `tools.py` — `get_dependencies(path)` → extract import chunk for given file
- [ ] 5.7 `tools.py` — `get_file_summary(path)` → return pre-computed summary/docstring chunk
- [ ] 5.8 All tools return `ToolResult(tool_name, input, output, duration_ms)` — structured, loggable

**Backend — Orchestrator**
- [ ] 5.9 `orchestrator.py` — agent mode: parse query intent, select 2–3 relevant tools
- [ ] 5.10 `orchestrator.py` — execute selected tools sequentially, collect `List[ToolResult]`
- [ ] 5.11 `orchestrator.py` — stream each `ToolResult` as `chat.tool_use` WebSocket event
- [ ] 5.12 `orchestrator.py` — merge tool outputs → feed into Step 2 assembler (reuse Phase 3)
- [ ] 5.13 `orchestrator.py` — Step 3: single LiteLLM call with merged context (reuse Phase 3)
- [ ] 5.14 `memory.py` — store last 10 conversation turns (query + answer + tool calls)
- [ ] 5.15 `memory.py` — prepend last 3 turns to context for follow-up question awareness

**Frontend**
- [ ] 5.16 Mode toggle in `ChatPanel` header — `RAG` | `Agent` pill switch
- [ ] 5.17 `ToolCallCard` component — shows tool name, input, output preview, duration badge
- [ ] 5.18 `ToolCallCard` — collapsible: collapsed by default, expand on click
- [ ] 5.19 Tool call cards appear above the streamed answer in the message thread
- [ ] 5.20 Token usage + cost badge updates live as `chat.done` arrives

### Agent Orchestrator Logic

```
def run_agent(query, project_id, history):

    # STEP 1 — SEARCH (local tools, no LLM)
    tools_to_run = select_tools(query)   # rule-based, no LLM
    tool_results = []
    for tool in tools_to_run:
        result = execute_tool(tool, query, project_id)
        yield ToolUseEvent(result)        # stream to frontend
        tool_results.append(result)

    # STEP 2 — ASSEMBLE (local)
    context = assembler.build(tool_results, max_tokens=4000)

    # STEP 3 — SYNTHESIZE (1 LLM call)
    async for token in litellm.stream(context, query, history):
        yield ChatTokenEvent(token)

    yield ChatDoneEvent(sources, total_tokens, cost_usd)
```

### Tool Selection Rules (no LLM needed)

| Query contains | Tools selected |
|---|---|
| "how does X work" | `search_codebase`, `find_symbol`, `get_dependencies` |
| "show me the X function" | `find_symbol`, `read_file` |
| "what files are in X" | `list_directory`, `search_codebase` |
| "where is X used" | `grep_codebase`, `search_codebase` |
| "explain X file" | `get_file_summary`, `read_file` |
| (default) | `search_codebase` only → falls back to RAG |

### Acceptance Criteria

- [ ] Agent mode answers "How does authentication work?" using 2–3 tools before synthesizing
- [ ] Each tool call appears as a `ToolCallCard` in the UI before the answer streams
- [ ] Total LLM calls per agent query = exactly 1 (verified by `llm_usage.jsonl`)
- [ ] Conversation memory: follow-up "what about the tests?" correctly references prior answer
- [ ] All 7 tools have unit tests with a real indexed test repo fixture

---

## Phase 6 — Hardening, Testing & Portfolio Presentation

**Goal:** Make the project demo-ready, resilient, and impressive to any engineer who reads the code or watches the demo.

### Tasks

**Robustness**
- [ ] 6.1 Error handling — invalid GitHub URLs, 404 repos, private repos without token
- [ ] 6.2 Error handling — binary-only repos, empty repos, repos with no supported languages
- [ ] 6.3 Error handling — LLM API key missing → graceful fallback message in UI
- [ ] 6.4 Rate limiting — `slowapi` on `POST /api/projects` (max 5/min per IP)
- [ ] 6.5 Timeout handling — indexing jobs > 10 min are cancelled with a clear error

**Testing**
- [ ] 6.6 `test_chunker.py` — test all chunk types across Python, TS, Go
- [ ] 6.7 `test_retriever.py` — test dense, BM25, RRF fusion with fixture data
- [ ] 6.8 `test_api.py` — test all REST endpoints with `httpx` async client
- [ ] 6.9 `test_agent.py` — test all 7 tools + orchestrator with mock project
- [ ] 6.10 `test_websocket.py` — test streaming chat + indexing progress events
- [ ] 6.11 Achieve >80% backend test coverage (`pytest-cov`)

**Docker & Deployment**
- [ ] 6.12 `Dockerfile` for backend — multi-stage, pre-warm embedding model in build
- [ ] 6.13 `Dockerfile` for frontend — Vite build → nginx static serve
- [ ] 6.14 `docker-compose.yml` — backend + frontend + shared volume for `./data/`
- [ ] 6.15 `make docker-up` command — one command to start full stack

**Portfolio Presentation**
- [ ] 6.16 `README.md` — architecture diagram (Mermaid), feature list, setup guide, screenshots
- [ ] 6.17 Pre-index 3 demo repos at startup: `fastapi/fastapi`, `facebook/react`, this project itself
- [ ] 6.18 `scripts/seed_demos.py` — script to index demo repos on first run
- [ ] 6.19 Performance profiling — `py-spy` flamegraph on indexing, fix top bottleneck
- [ ] 6.20 Record 3-minute demo video: submit URL → watch indexing → chat → click citations → scatter

### Demo Script (for video / interviews)

```
1. Open app → submit https://github.com/fastapi/fastapi
2. Watch indexing progress bar advance through 5 stages
3. UMAP scatter appears — point out cluster regions (routing, models, deps)
4. Ask: "How does dependency injection work in FastAPI?"
5. Show ToolCallCards appearing (search_codebase, find_symbol, get_dependencies)
6. Answer streams in — click a citation chip
7. File opens in Preview Mode at exact line — point pulses in scatter
8. Ask follow-up: "What about the test utilities?" — show memory working
9. Toggle to RAG mode — show same query, no tool cards, same quality answer
```

### Acceptance Criteria

- [ ] `docker compose up` starts full stack with zero manual steps
- [ ] 3 demo repos are pre-indexed and queryable on first launch
- [ ] Test suite passes with >80% coverage
- [ ] `README.md` contains: architecture diagram, feature list, setup instructions, demo GIF
- [ ] No unhandled exceptions reachable via normal UI interactions
- [ ] Demo video is recorded and linked in README

---

## Milestone Summary

| Phase | Name | Key Deliverable | Est. Sessions | Status |
|---|---|---|---|---|
| 1 | Scaffold | Running skeleton, 3-pane UI, health endpoint | 1–2 | ⬜ Not Started |
| 2 | Ingestion | AST chunking, ChromaDB, UMAP, WebSocket progress | 3–4 | ⬜ Not Started |
| 3 | RAG Chat | 3-step pipeline, streaming, citations, cost logging | 3–4 | ⬜ Not Started |
| 4 | Frontend | UMAP scatter, file preview, citation linking, dark mode | 3–4 | ⬜ Not Started |
| 5 | Agent | Tool registry, tool trace UI, conversation memory | 2–3 | ⬜ Not Started |
| 6 | Portfolio | Tests, Docker, README, demo video, seed data | 2–3 | ⬜ Not Started |

**Total estimated sessions: 14–20**

---

## Quick Reference — The 3-Step Pipeline

> This is the single most important concept in the codebase. Every query — RAG or Agent — follows this exact flow.

```
┌─────────────────────────────────────────────────────┐
│  STEP 1: SEARCH          local · free · fast        │
│  Tools: search_codebase, find_symbol, grep, etc.    │
│  Output: List[Chunk] — raw retrieved candidates     │
├─────────────────────────────────────────────────────┤
│  STEP 2: ASSEMBLE        local · free · fast        │
│  FlashRank rerank → token budget → citation map     │
│  Output: assembled_context string (≤4,000 tokens)   │
├─────────────────────────────────────────────────────┤
│  STEP 3: SYNTHESIZE      1 LLM call · ~$0.001       │
│  LiteLLM → claude-haiku-3-5 → stream tokens         │
│  Output: streamed answer + sources + cost           │
└─────────────────────────────────────────────────────┘
```