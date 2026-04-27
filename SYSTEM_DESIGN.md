# SYSTEM_DESIGN.md
# AI-Powered Codebase Analyzer — System Design

> **Portfolio Project** | Stack: Python · FastAPI · ChromaDB · React · TypeScript  
> **Core Philosophy:** Local Heavy, Cloud Light — the LLM is called exactly **once** per query, only for final synthesis. All parsing, embedding, retrieval, and reranking run locally at zero API cost.

---

## 1. Architectural Overview

A **decoupled, layered architecture**: the Python backend owns all computation (cloning, AST parsing, embedding, retrieval, reranking), while the React frontend owns presentation. They communicate over a **REST + WebSocket hybrid** — REST for data fetching, WebSocket for streaming responses and indexing progress.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          WEB FRONTEND (React + TypeScript)           │
│                                                                      │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌────────────────┐  │
│  │   LEFT PANE      │  │   MIDDLE PANE        │  │  RIGHT PANE    │  │
│  │                  │  │                      │  │                │  │
│  │  File Explorer   │  │  • UMAP Scatter Plot │  │  AI Chat UI    │  │
│  │  • Collapsible   │  │  • Syntax Previewer  │  │  • Streaming   │  │
│  │    file tree     │  │  • Chunk Inspector   │  │  • Citations   │  │
│  │  • Language tags │  │  • Cluster labels    │  │  • Step trace  │  │
│  └────────┬─────────┘  └──────────┬──────────┘  └───────┬────────┘  │
│           └─────────────────────── ┴ ───────────────────┘            │
│                                    │                                  │
│              REST (TanStack Query) + WebSocket (custom hook)         │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│                        PYTHON BACKEND (FastAPI)                      │
│                                                                      │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐  │
│  │  INGESTION      │   │  SEARCH-FIRST    │   │  AGENT           │  │
│  │  PIPELINE       │   │  RAG ENGINE      │   │  ORCHESTRATOR    │  │
│  │                 │   │                  │   │                  │  │
│  │  1. Git Clone   │   │  Step 1: Search  │   │  3-Step Linear:  │  │
│  │  2. AST Parse   │   │  (Dense + BM25)  │   │  Search →        │  │
│  │  3. Chunk       │   │  Step 2: Assemble│   │  Assemble →      │  │
│  │  4. Embed       │   │  (Rerank+Budget) │   │  Synthesize      │  │
│  │  5. UMAP/HDBSCAN│   │  Step 3: Synth   │   │  (1 LLM call)    │  │
│  └────────┬────────┘   └────────┬─────────┘   └────────┬─────────┘  │
│           └────────────────────── ┴ ──────────────────┘              │
│                                    │                                  │
│              ┌─────────────────────▼──────────────────┐              │
│              │         ChromaDB  (local, persistent)   │              │
│              │         SQLite    (project metadata)    │              │
│              └────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### 2.1 Ingestion Pipeline

The ingestion pipeline transforms raw source code into semantically rich, retrievable chunks. It is the **portfolio's most technically impressive component** — showcasing AST parsing, local embeddings, and dimensionality reduction without any cloud dependency.

#### Stage 1 — Repository Acquisition
- **GitHub URL**: `GitPython` shallow-clone (`--depth=1`) into `/tmp/codebase_analyzer/{project_id}/`
- **Local Path**: Direct reference — no cloning needed
- `pathspec` provides `.gitignore`-aware walking — skips `node_modules`, `__pycache__`, `.git`, binaries, and lock files
- Progress events streamed to frontend via WebSocket during this stage

#### Stage 2 — AST-Based Intelligent Chunking

The key differentiator from naive RAG tutorials. Every file is parsed into its **semantic units** via `tree-sitter`, not split by character count.

```
Raw Source File  (.py / .ts / .js / .go / .rs)
        │
        ▼
┌──────────────────────┐
│   Language Router    │  detects via extension + magic bytes
└──────────┬───────────┘
           │
    ┌──────▼──────────────────────────────────────────┐
    │           tree-sitter AST Parser                │
    │                                                 │
    │  Node types extracted:                          │
    │  • function_definition  → 1 chunk per function  │
    │  • class_definition     → 1 chunk (sig+docstr)  │
    │  • method_definition    → 1 chunk per method    │
    │  • import_statement     → 1 combined chunk      │
    │  • module docstring     → 1 summary chunk       │
    │  • assignment (const)   → 1 config chunk        │
    └──────────────────────────────────┬──────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │     Chunk + Metadata    │
                          │  file_path              │
                          │  chunk_type             │
                          │  symbol_name            │
                          │  start_line / end_line  │
                          │  language               │
                          │  parent_class           │
                          │  docstring (if any)     │
                          └─────────────────────────┘
```

**Chunking Strategy by Type:**

| Chunk Type | Strategy | Token Limit |
|---|---|---|
| Function / Method | Full body + signature | 512 |
| Class | Signature + docstring + method stubs only | 256 |
| Imports block | All imports merged into one chunk | 128 |
| Oversized function | Sliding window, 20% overlap | 512 |
| Config / Constants | Full block | 256 |
| Markdown / Docs | Paragraph-boundary splitting | 512 |
| Unsupported language | Sliding window fallback | 512 |

#### Stage 3 — Embedding, Storage & Visualization Pre-computation
- `sentence-transformers` (`all-MiniLM-L6-v2`) embeds all chunks locally — **zero API cost**
- Chunks + metadata stored in ChromaDB (persistent local collection per project)
- **UMAP** reduces 384-dim embeddings → 2D coordinates — computed once, cached to `umap_coords.json`
- **HDBSCAN** clusters the 2D points — cluster labels stored alongside coordinates
- Project manifest written: `{ file_count, chunk_count, languages, index_timestamp, umap_ready }`

---

### 2.2 Search-First RAG Engine

The RAG engine follows a strict **3-step linear pipeline**. There is no iterative loop. The LLM is invoked exactly once — at Step 3. This is the core budget-control mechanism.

```
  USER QUERY
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 1 — BROAD SEARCH          (local, no API cost)    │
│                                                         │
│  ┌─────────────────────┐   ┌─────────────────────────┐  │
│  │  Dense Retrieval    │   │  Sparse Retrieval       │  │
│  │  ChromaDB vector    │   │  BM25 (rank-bm25)       │  │
│  │  search  top-k=20   │   │  keyword match top-k=20 │  │
│  └──────────┬──────────┘   └────────────┬────────────┘  │
│             └──────────────┬────────────┘               │
│                            ▼                            │
│              Reciprocal Rank Fusion → top-20 merged     │
└────────────────────────────┬────────────────────────────┘
                             │
                    ┌────────▼────────────────────────────┐
│  STEP 2 — CONTEXT ASSEMBLY      (local, no API cost)    │
│                                                         │
│  FlashRank cross-encoder reranker  top-20 → top-5       │
│  Token budget enforcer             max 4,000 tokens     │
│  Deduplicator                      remove overlap       │
│  Source citation builder           file + line refs     │
└────────────────────────────┬────────────────────────────┘
                             │
                    ┌────────▼────────────────────────────┐
│  STEP 3 — SYNTHESIS             (1 LLM call, ~$0.001)   │
│                                                         │
│  LiteLLM → claude-haiku-3-5 (default)                  │
│           → ollama/codellama:7b (offline fallback)      │
│                                                         │
│  Input:  assembled context + user query                 │
│  Output: streamed answer tokens via WebSocket           │
│          + source citations attached to final message   │
└─────────────────────────────────────────────────────────┘
```

> **If Step 1 returns zero results:** a single lightweight LLM call generates a HyDE (Hypothetical Document Embedding) — a synthetic answer used to re-query ChromaDB. This is the only permitted second loop, and only fires on empty retrieval.

**Budget Guarantee:** Every query costs at most 1 LLM call. Token usage is logged to `logs/llm_usage.jsonl` after every synthesis.

---

### 2.3 Agent Orchestrator

The agent is **not a chatbot wrapper** — it is a structured reasoning engine that uses the same 3-step Search-First strategy as the RAG engine, but exposes it through a tool-calling interface. This makes the agent's reasoning transparent and inspectable in the UI.

```
User Query: "How does authentication work in this project?"
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 1 — SEARCH          (local tools, no LLM cost)    │
│                                                         │
│  Tool: search_codebase("authentication login jwt")      │
│    → returns ranked chunks from ChromaDB + BM25         │
│                                                         │
│  Tool: find_symbol("authenticate" | "verify_token")     │
│    → pinpoints exact function definitions               │
│                                                         │
│  Tool: get_dependencies("auth.py")                      │
│    → maps import graph for auth module                  │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│  STEP 2 — ASSEMBLE        (local, no LLM cost)          │
│                                                         │
│  Merge tool outputs → deduplicate → rank by relevance   │
│  Apply 4,000 token budget cap                           │
│  Build source citation map { symbol → file:line }       │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│  STEP 3 — SYNTHESIZE      (1 LLM call)                  │
│                                                         │
│  LiteLLM sends assembled context to claude-haiku-3-5    │
│  Streams answer tokens → WebSocket → Chat UI            │
│  Attaches citations → clickable in frontend             │
└─────────────────────────────────────────────────────────┘
```

**Tool Registry** — all tools execute locally, return structured data:

| Tool | Input | Output | Cost |
|---|---|---|---|
| `search_codebase` | query string | ranked `List[Chunk]` | free |
| `find_symbol` | symbol name | `List[Chunk]` matching definition | free |
| `read_file` | file path | raw file text (sandboxed) | free |
| `list_directory` | dir path | `List[FileNode]` | free |
| `grep_codebase` | regex pattern | matching lines + file paths | free |
| `get_dependencies` | file path | import graph for that file | free |
| `get_file_summary` | file path | pre-computed summary chunk | free |
| `explain_chunk` | chunk id | full chunk text + metadata | free |

> **Portfolio Note:** The tool execution trace is streamed to the frontend as `chat.tool_use` events, making the agent's reasoning fully visible — a key differentiator for demo purposes.

---

### 2.4 Frontend ↔ Backend Communication

#### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/projects` | Submit GitHub URL or local path; triggers async indexing |
| `GET` | `/api/projects` | List all previously indexed projects |
| `GET` | `/api/projects/{id}` | Get project status, manifest, and language breakdown |
| `GET` | `/api/projects/{id}/tree` | Full file tree as nested JSON |
| `GET` | `/api/projects/{id}/file?path=` | Raw file content (sandboxed to project dir) |
| `GET` | `/api/projects/{id}/embeddings` | 2D UMAP coords + cluster labels for scatter plot |
| `DELETE` | `/api/projects/{id}` | Delete project, ChromaDB collection, and cloned files |
| `GET` | `/api/health` | Health check — returns version + uptime |

#### WebSocket — `/ws/{project_id}`

| Event | Direction | Payload |
|---|---|---|
| `chat.message` | Client → Server | `{ query, mode: "rag" \| "agent" }` |
| `chat.token` | Server → Client | `{ token }` — streamed word by word |
| `chat.tool_use` | Server → Client | `{ tool_name, tool_input, tool_output, duration_ms }` |
| `chat.done` | Server → Client | `{ sources: [{ file, line, symbol }], total_tokens, cost_usd }` |
| `index.progress` | Server → Client | `{ stage, percent, current_file, chunks_so_far }` |
| `index.done` | Server → Client | `{ project_id, chunk_count, duration_ms }` |
| `error` | Server → Client | `{ code, message }` |

---

### 2.5 Middle Pane — Live Vector Visualization

The middle pane is the **visual centrepiece of the portfolio demo**. It renders the entire codebase as a navigable 2D map of meaning.

```
  ChromaDB embeddings (384-dim)
          │
          ▼  [computed once at index time, cached to umap_coords.json]
     UMAP 2D projection
          │
          ▼
     HDBSCAN clustering  →  auto-labeled cluster regions
          │
          ▼
  GET /api/projects/{id}/embeddings
          │
          ▼
  Observable Plot scatter (canvas renderer, handles 50k+ points)
```

**Interaction Model:**

| User Action | UI Response |
|---|---|
| Hover a point | Tooltip: symbol name, file path, chunk type |
| Click a point | File opens in middle pane preview; file highlighted in left pane |
| Send a chat message | Retrieved chunks **pulse** with a ring animation |
| Toggle color mode | Switch between: chunk type / language / cluster |
| Click cluster label | Filter scatter to show only that cluster |

**Two Middle Pane Modes** (tab-switched):
- **Map Mode** — UMAP scatter plot (default on project load)
- **Preview Mode** — Syntax-highlighted file viewer (Shiki), activated by clicking any file or citation

---

## 3. End-to-End Data Flow

```
 INDEXING FLOW
 ─────────────────────────────────────────────────────────────
  [1] User submits GitHub URL via frontend form
       │
  [2] POST /api/projects  →  backend creates project record (SQLite)
       │                      returns { project_id, status: "cloning" }
       │
  [3] Async task: GitPython shallow-clones repo → /tmp/{project_id}/
       │           WebSocket streams  index.progress { stage: "cloning" }
       │
  [4] pathspec walker builds file list, filters ignored paths
       │           WebSocket streams  index.progress { stage: "walking" }
       │
  [5] tree-sitter AST chunker processes each file → List[Chunk]
       │           WebSocket streams  index.progress { stage: "chunking",
       │                                               current_file, percent }
       │
  [6] sentence-transformers embeds all chunks in batches (local)
       │           ChromaDB stores chunks + metadata + vectors
       │           WebSocket streams  index.progress { stage: "embedding" }
       │
  [7] UMAP + HDBSCAN compute 2D layout → saved to umap_coords.json
       │           WebSocket streams  index.done { chunk_count, duration_ms }
       │
  [8] Project status → "READY" in SQLite

 QUERY FLOW
 ─────────────────────────────────────────────────────────────
  [9]  User types query in Chat panel (right pane)
       │
  [10] WebSocket: chat.message { query, mode: "rag" | "agent" }
       │
  [11] Step 1 — Search: ChromaDB dense + BM25 sparse → RRF merge → top-20
       │
  [12] Step 2 — Assemble: FlashRank rerank → top-5
       │                   token budget check (tiktoken, max 4k)
       │                   citation map built
       │
  [13] Step 3 — Synthesize: LiteLLM → claude-haiku-3-5 (1 call)
       │         WebSocket streams: chat.token { token } per word
       │
  [14] WebSocket: chat.done { sources, total_tokens, cost_usd }
       │
  [15] Frontend renders answer + citation chips
       │
  [16] User clicks citation chip
       │        → middle pane switches to Preview Mode
       │        → file opens at exact line number (Shiki highlight)
       │        → corresponding point pulses in UMAP scatter
```

---

## 4. Security & Isolation

| Concern | Mitigation |
|---|---|
| Project data isolation | Each project gets a UUID-namespaced ChromaDB collection |
| Path traversal | All `read_file` tool calls are sandboxed to `/tmp/{project_id}/` |
| Code execution | Zero — static analysis only, no `eval`, no subprocess on user code |
| Repo cleanup | DELETE endpoint removes ChromaDB collection + cloned files |
| Private repos | Supported via `GITHUB_TOKEN` env var passed to GitPython |

---

## 5. Portfolio Showcase Points

These are the talking points that make this project stand out in interviews:

| Feature | Why It's Impressive |
|---|---|
| AST-based chunking | Retrieves exact functions, not random text windows |
| Hybrid retrieval (Dense + BM25) | Combines semantic and keyword search — industry standard |
| Local reranking (FlashRank) | Cross-encoder quality with zero API cost |
| UMAP + HDBSCAN visualization | Makes the invisible (embeddings) visible and interactive |
| 1 LLM call per query | Demonstrates cost discipline and system design maturity |
| Streaming WebSocket responses | Real-time UX, not a loading spinner |
| Tool trace in UI | Agent reasoning is transparent, not a black box |
| LiteLLM abstraction | Swap models without code changes — production thinking |

---

## 6. Upgrade Path (When Budget Allows)

| Current | Upgrade | Trigger |
|---|---|---|
| `all-MiniLM-L6-v2` local | `text-embedding-3-small` (OpenAI) | Accuracy complaints |
| `claude-haiku-3-5` | `claude-sonnet-4` | Complex multi-file reasoning |
| ChromaDB local | Qdrant (self-hosted Docker) | >100k chunks |
| SQLite | PostgreSQL | Multi-user support |
| Sync UMAP | Background Celery task | Repos >10k files |