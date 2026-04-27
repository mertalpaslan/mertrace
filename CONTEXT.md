# CONTEXT.md
# AI Codebase Analyzer — Session State & Progress Tracker

> This file is the **living memory** of the project.
> Update it at the start and end of every coding session.
> It is the first file to read when resuming work.

---

## Project Identity

| Field | Value |
|---|---|
| **Project Name** | AI-Powered Codebase Analyzer |
| **Version** | 0.1.0 — Planning Complete |
| **Architecture Doc** | `SYSTEM_DESIGN.md` |
| **Roadmap** | `PROJECT_MAP.md` |
| **Tech Stack** | `TECH_STACK.md` |
| **Last Updated** | 2025-01-25 |
| **Current Phase** | Phase 5 — Agentic Workflow Complete |

---

## Core Principles (Non-Negotiable)

These rules govern every implementation decision:

1. **Linear over Iterative** — Agent uses 3-step Search-First strategy.
   - Step 1: Broad semantic search (local, ChromaDB)
   - Step 2: Context assembly (local, reranker)
   - Step 3: Single-pass LLM synthesis (one API call)
   - Second loop ONLY if Step 1 returns zero results.

2. **Local Heavy, Cloud Light** — All of the following run locally:
   - AST parsing (tree-sitter)
   - Embedding (all-MiniLM-L6-v2 via sentence-transformers)
   - Reranking (FlashRank cross-encoder)
   - UMAP + HDBSCAN visualization
   - BM25 sparse retrieval
   - The LLM is called **once** per query, for synthesis only.

3. **Atomic Modules** — No file exceeds 400 lines.
   - Plan the split before writing any module.
   - Prefer many small, focused files over large monoliths.

---

## Phase Progress

| Phase | Name | Status | Completion |
|---|---|---|---|
| 0 | Foundation Docs | ✅ Complete | 100% |
| 1 | Scaffold & Dev Environment | ✅ Complete | 100% |
| 2 | Ingestion Pipeline | ✅ Complete | 100% |
| 3 | Basic RAG Chat | ✅ Complete | 100% |
| 4 | Frontend Polish & Viz | ✅ Complete | 100% |
| 5 | Agentic Workflow | ✅ Complete | 100% |
| 6 | Hardening & Portfolio | ⬜ Not Started | 0% |

---

## Current Session State

### What Was Just Completed (Session 002 — Phase 1)
- [x] Full backend directory structure created
- [x] `backend/pyproject.toml` — uv project with all deps (greenlet fix for Py3.14)
- [x] `backend/app/core/config.py` — pydantic-settings config
- [x] `backend/app/core/logging.py` — JSON structured logging
- [x] `backend/app/models/project.py` — SQLModel Project table
- [x] `backend/app/models/chunk.py` — Chunk, ToolResult, Citation schemas
- [x] `backend/app/api/deps.py` — DB engine, session dep, ChromaDB singleton
- [x] `backend/app/api/routes/projects.py` — CRUD endpoints
- [x] `backend/app/api/routes/files.py` — tree, file content, embeddings endpoints
- [x] `backend/app/api/routes/chat.py` — WebSocket endpoint (Phase 1 echo)
- [x] `backend/app/main.py` — FastAPI app with lifespan, CORS, routers
- [x] `backend/tests/test_api.py` — 5 API tests (all passing)
- [x] `backend/tests/conftest.py` — pytest fixtures with in-memory DB
- [x] Frontend scaffold: package.json, vite.config.ts, tsconfig, tailwind
- [x] `frontend/src/api/client.ts` — typed API client
- [x] `frontend/src/store/appStore.ts` — Zustand global state
- [x] `frontend/src/hooks/useWebSocket.ts` — WS hook with exponential backoff
- [x] `frontend/src/hooks/useProject.ts` — React Query hooks
- [x] `frontend/src/components/` — FileExplorer, VectorViz, FilePreview, ChatPanel, MessageBubble, ProjectBar
- [x] `frontend/src/App.tsx` — 3-pane layout
- [x] `Makefile` — dev, test, lint, format, clean targets
- [x] `env.example` — environment template
- [x] **5/5 backend tests passing**

### What Was Just Completed (Session 003 — Phase 2)
- [x] `backend/app/ingestion/cloner.py` — shallow git clone with full-clone fallback
- [x] `backend/app/ingestion/walker.py` — .gitignore-aware walker, binary skip, tree builder
- [x] `backend/app/ingestion/chunker.py` — tree-sitter AST chunker (Python/TS/JS/Go) + fallback
- [x] `backend/app/ingestion/embedder.py` — sentence-transformers batched embed + ChromaDB upsert
- [x] `backend/app/ingestion/umap_builder.py` — UMAP + HDBSCAN, saves umap_coords.json
- [x] `backend/app/ingestion/pipeline.py` — 5-stage orchestrator with async WebSocket progress
- [x] `backend/app/api/routes/projects.py` — wired `run_pipeline` as background task
- [x] `backend/app/api/routes/files.py` — serves real file tree from disk
- [x] `backend/app/api/routes/chat.py` — WebSocket registry + broadcast for progress events
- [x] `backend/tests/test_ingestion.py` — 12 walker + chunker unit tests
- [x] Fixed `pathspec` deprecation: `gitwildmatch` → `gitignore`
- [x] Fixed `BackgroundTasks` test isolation via `NoOpBackgroundTasks` override
- [x] **17/17 tests passing in 0.12s**

### What Was Just Completed (Session 004 — Phase 3)
- [x] `backend/app/rag/retriever.py` — hybrid semantic+BM25 with Reciprocal Rank Fusion
- [x] `backend/app/rag/reranker.py` — FlashRank cross-encoder with graceful fallback
- [x] `backend/app/rag/context_assembler.py` — token-budget packing, file grouping, citations
- [x] `backend/app/rag/synthesizer.py` — streaming LiteLLM call with system prompt
- [x] `backend/app/api/routes/chat.py` — full RAG pipeline wired into WebSocket handler
- [x] `backend/tests/test_rag.py` — 13 tests: RRF, reranker, assembler
- [x] Fixed `Citation` model mismatch (added `index`, `chunk_type`)
- [x] **30/30 tests passing in 0.56s**

### What Was Just Completed (Session 004 — Phase 4)
- [x] `FilePreview.tsx` — auto-scroll to highlighted lines on citation click
- [x] `useWebSocket.ts` — exposes `status: WSStatus` (disconnected/connecting/connected)
- [x] `ProjectBar.tsx` — live progress bar with stage labels + WS status indicator; auto-selects new project; invalidates query cache on done/error
- [x] `ChatPanel/index.tsx` — passes conversation history (last 6 turns) to WS; disables input when WS not connected
- [x] `App.tsx` — scatter color mode selector (type/language/cluster) in middle pane header
- [x] `package.json` + `tsconfig.json` — fixed escaped-quote corruption; added `uuid` dep
- [x] TypeScript: 0 errors in source files
- [x] **30/30 backend tests still passing**

### What Was Just Completed (Session 005 — Phase 5)
- [x] `backend/app/agent/tools.py` — 4 tools: `search_code`, `read_file`, `grep_symbol`, `list_files`; path traversal protection; `run_tool` dispatcher
- [x] `backend/app/agent/memory.py` — sliding window memory (20 turns / 4000 token budget); per-project store
- [x] `backend/app/agent/orchestrator.py` — 3-step linear agent: tool rounds (max 3) → streaming synthesis; stores turns in memory
- [x] `backend/app/api/routes/chat.py` — agent mode wired; `memory.clear` WS message; `agent.tool_start`/`agent.tool_done` events streamed
- [x] `frontend/src/components/ChatPanel/MessageBubble.tsx` — tool call cards with expand/collapse, error state, input/output display
- [x] `frontend/src/components/ChatPanel/index.tsx` — handles `agent.tool_start`/`agent.tool_done`; buffers tool calls; passes to `finalizeMessage`
- [x] `frontend/src/store/appStore.ts` — `finalizeMessage` accepts optional `toolCalls` param
- [x] `backend/tests/test_agent.py` — 15 tests: memory, read_file, grep_symbol, list_files, run_tool
- [x] **45/45 tests passing in 0.51s**

### What To Do Next (Phase 6 — Hardening & Portfolio)
- [ ] Rate limiting on indexing endpoint
- [ ] Error boundary in React
- [ ] `docker-compose.yml` — production-ready compose with backend + frontend
- [ ] `README.md` — full setup guide, architecture diagram, demo GIF
- [ ] `.github/workflows/ci.yml` — GitHub Actions: backend tests + TS typecheck
- [ ] Ruff lint pass — clean up any warnings
- [ ] Add `useProject.ts` polling for project status during indexing

---

## Architecture Decisions Log

### ADR-001: ChromaDB as Primary Vector Store
- **Decision:** Use ChromaDB with local persistence
- **Rationale:** Zero infrastructure, free, persistent across restarts,
  built-in embedding support
- **Trade-off:** Not horizontally scalable; acceptable for portfolio scope
- **Revisit When:** Chunk count exceeds 100,000

### ADR-002: tree-sitter for AST Chunking
- **Decision:** Use tree-sitter + tree-sitter-languages for all parsing
- **Rationale:** Single library supports 40+ languages, runs fully local,
  produces accurate AST nodes for function/class extraction
- **Trade-off:** Requires compiled grammars; `tree-sitter-languages`
  bundle resolves this
- **Revisit When:** Need language not in bundle

### ADR-003: 3-Step Linear Agent (No ReAct Loop)
- **Decision:** Replace ReAct loop with Search → Assemble → Synthesize
- **Rationale:** ReAct loops make 3-10 LLM calls per query; our strategy
  makes exactly 1. Saves ~90% of API cost per query.
- **Trade-off:** Less autonomous reasoning for deeply nested questions
- **Revisit When:** User explicitly requests deep multi-hop reasoning mode

### ADR-004: LiteLLM as LLM Abstraction Layer
- **Decision:** All LLM calls go through LiteLLM
- **Rationale:** Swap between Claude, OpenAI, and local Ollama without
  changing application code. Critical for budget management.
- **Trade-off:** Thin extra dependency
- **Revisit When:** Never — this is strictly additive

### ADR-005: Zustand over Redux for Frontend State
- **Decision:** Use Zustand for global state management
- **Rationale:** ~1KB library, no boilerplate, handles WebSocket state
  updates efficiently without re-render storms
- **Trade-off:** Less tooling than Redux DevTools
- **Revisit When:** App grows to multi-user or complex state graphs

---

## Known Constraints & Gotchas

### Backend
- `tree-sitter` requires compiled `.so` grammars — use
  `tree-sitter-languages` to avoid manual compilation
- ChromaDB's default embedding function downloads model on first run —
  pre-warm in Docker build step
- UMAP is slow on first run for large repos (>5000 chunks) — run async,
  cache results to disk as `umap_coords.json`
- `gitpython` shallow clone (`--depth=1`) does not support all repo types —
  add fallback to full clone with warning

### Frontend
- WebSocket reconnection must be handled manually — implement exponential
  backoff in the custom `useWebSocket` hook
- Shiki syntax highlighter is async — wrap in Suspense or use
  `codeToHtml()` with loading state
- Observable Plot does not support WebGL by default for >10k points —
  use canvas renderer with `dot()` mark

### API Budget
- Default model: `claude-haiku-3-5` (~$0.001 per query at 4k context)
- Hard limit: 4,000 tokens max context sent to LLM per query
- Token counter must run before every LLM call (use `tiktoken`)
- Log every LLM call with token count to `logs/llm_usage.jsonl`

---

## File Registry

> Track every file created. Update this table each session.

| File | Status | Description |
|---|---|---|
| `SYSTEM_DESIGN.md` | ✅ Created | Architecture & system design |
| `PROJECT_MAP.md` | ✅ Created | Implementation roadmap |
| `TECH_STACK.md` | ✅ Created | Technology choices & rationale |
| `CONTEXT.md` | ✅ Created | This file — session memory |
| `backend/app/main.py` | ✅ Created | FastAPI entry point |
| `backend/app/core/config.py` | ✅ Created | App configuration |
| `backend/app/core/logging.py` | ✅ Created | JSON structured logging |
| `backend/app/models/project.py` | ✅ Created | SQLModel Project table |
| `backend/app/models/chunk.py` | ✅ Created | Chunk / ToolResult / Citation schemas |
| `backend/app/api/deps.py` | ✅ Created | DB engine + ChromaDB singleton |
| `backend/app/api/routes/projects.py` | ✅ Created | Project CRUD endpoints |
| `backend/app/api/routes/files.py` | ✅ Created | File tree / content / embeddings |
| `backend/app/api/routes/chat.py` | ✅ Created | WebSocket chat endpoint |
| `backend/tests/test_api.py` | ✅ Created | 5 passing API tests |
| `backend/tests/conftest.py` | ✅ Created | pytest DB fixtures |
| `backend/pyproject.toml` | ✅ Created | uv project + all deps |
| `frontend/src/App.tsx` | ✅ Created | 3-pane root component |
| `frontend/src/api/client.ts` | ✅ Created | Typed API client |
| `frontend/src/store/appStore.ts` | ✅ Created | Zustand global state |
| `frontend/src/hooks/useWebSocket.ts` | ✅ Created | WS hook w/ backoff |
| `frontend/src/hooks/useProject.ts` | ✅ Created | React Query hooks |
| `frontend/src/components/FileExplorer/` | ✅ Created | Left pane |
| `frontend/src/components/VectorViz/` | ✅ Created | Middle pane (map + preview) |
| `frontend/src/components/ChatPanel/` | ✅ Created | Right pane |
| `frontend/src/components/ProjectBar.tsx` | ✅ Created | Project selector + form |
| `Makefile` | ✅ Created | Dev task runner |
| `env.example` | ✅ Created | Environment template |
| `backend/app/ingestion/cloner.py` | ✅ Created | Shallow git clone + local copy |
| `backend/app/ingestion/walker.py` | ✅ Created | .gitignore-aware file walker |
| `backend/app/ingestion/chunker.py` | ✅ Created | tree-sitter AST + fallback chunker |
| `backend/app/ingestion/embedder.py` | ✅ Created | Batched embed + ChromaDB upsert |
| `backend/app/ingestion/pipeline.py` | ✅ Created | 5-stage async pipeline |
| `backend/app/ingestion/umap_builder.py` | ✅ Created | UMAP + HDBSCAN coords |
| `backend/app/rag/retriever.py` | ✅ Created | Hybrid semantic+BM25+RRF |
| `backend/app/rag/reranker.py` | ✅ Created | FlashRank with fallback |
| `backend/app/rag/context_assembler.py` | ✅ Created | Token-budget context packer |
| `backend/app/rag/synthesizer.py` | ✅ Created | Streaming LiteLLM synthesis |
| `backend/app/agent/orchestrator.py` | ⬜ Pending | 3-step agent |
| `backend/app/agent/tools.py` | ⬜ Pending | Agent tool registry |
| `backend/app/agent/memory.py` | ⬜ Pending | Conversation memory |
| `docker-compose.yml` | ⬜ Pending | Container orchestration |

---

## Session Log

### Session 001 — Planning & Architecture
- **Date:** 2025-01-01
- **Completed:** Architecture docs, roadmap, tech stack, rules
- **Next:** Phase 1 scaffold

### Session 002 — Phase 1: Full Scaffold
- **Date:** 2025-01-25
- **Completed:**
  - Full backend: FastAPI + SQLModel + ChromaDB + all routes
  - Full frontend: React + Zustand + React Query + 3-pane UI
  - 5/5 backend tests passing
  - Fixed Python 3.14 compatibility (tree-sitter-languages → individual packages, greenlet explicit dep)
  - Fixed quote escaping issue in file creation tooling
- **Decisions Made:**
  - Switched from `tree-sitter-languages` to individual `tree-sitter-*` packages (no Py3.14 wheel)
  - Added `greenlet>=3.0.0` explicitly (SQLAlchemy async requires it, not auto-installed on Py3.14)
  - Used in-memory SQLite for tests via `conftest.py` fixtures (no test DB pollution)
- **Next Session Goal:** Phase 2 — Ingestion pipeline (cloner → walker → chunker → embedder → UMAP)

---

## How To Resume This Project

1. Read this file (`CONTEXT.md`) first — always.
2. Check **Current Session State** → **What To Do Next**.
3. Check **Phase Progress** table for overall status.
4. Review the last entry in **Session Log** for context.
5. Before writing any file, check **File Registry** to avoid duplication.
6. After each session, update:
   - Phase Progress table
   - Current Session State
   - File Registry
   - Session Log (add new entry)