# TECH_STACK.md
# AI-Powered Codebase Analyzer — Technology Stack

> Philosophy: **Local Heavy, Cloud Light.**
> Every CPU-bound task runs locally. The LLM is a synthesis tool, not a workhorse.

---

## 1. Backend (Python)

### Core Framework
| Library | Version | Role | Why |
|---|---|---|---|
| `fastapi` | 0.111+ | API + WebSocket server | Async-native, fastest Python web framework, excellent WebSocket support |
| `uvicorn` | 0.29+ | ASGI server | Production-grade, works with uvloop for max throughput |
| `pydantic` v2 | 2.7+ | Data validation & models | 2x faster than v1, native JSON schema generation |
| `python-dotenv` | 1.0+ | Env config management | Simple, universal |

### Ingestion & Parsing
| Library | Version | Role | Why |
|---|---|---|---|
| `gitpython` | 3.1+ | Repo cloning | Pythonic Git interface, supports shallow clone |
| `pathspec` | 0.12+ | .gitignore-aware walking | Correct gitignore rule parsing, lightweight |
| `tree-sitter` | 0.22+ | AST parsing engine | Universal, supports 40+ languages, runs fully local |
| `tree-sitter-languages` | 1.10+ | Pre-built grammar bundle | One install for Python/JS/TS/Go/Rust grammars |
| `chardet` | 5.2+ | File encoding detection | Prevents UnicodeDecodeError on mixed repos |
| `tiktoken` | 0.7+ | Token counting | Fast BPE tokenizer, used for chunk size budgeting |

### Vector Store & Embeddings
| Library | Version | Role | Why |
|---|---|---|---|
| `chromadb` | 0.5+ | Local vector store | Zero-infra, persistent, built-in embedding model |
| `sentence-transformers` | 3.0+ | Local embedding model | `all-MiniLM-L6-v2` is fast, accurate, 100% free |

> **Embedding Model Choice:** `all-MiniLM-L6-v2` (384 dims).
> - 80MB model, runs on CPU in ~5ms per chunk.
> - No API calls. No cost. No rate limits.
> - Upgrade path: swap to `text-embedding-3-small` via LiteLLM when budget allows.

### Retrieval & Reranking
| Library | Version | Role | Why |
|---|---|---|---|
| `rank-bm25` | 0.2+ | Sparse BM25 retrieval | Keyword-exact matching, complements dense search |
| `flashrank` | 0.2+ | Local cross-encoder reranker | Runs on CPU, reranks top-20 → top-5 with no API cost |

> **Hybrid Retrieval Strategy:**
> Dense (ChromaDB) + Sparse (BM25) → fused via Reciprocal Rank Fusion → reranked by FlashRank.
> All local. Zero LLM calls during retrieval.

### Visualization (Backend Computation)
| Library | Version | Role | Why |
|---|---|---|---|
| `umap-learn` | 0.5+ | Dimensionality reduction | Best quality 2D projection of embeddings |
| `hdbscan` | 0.8+ | Density-based clustering | No need to specify cluster count, handles noise |
| `numpy` | 1.26+ | Numerical operations | Foundation for UMAP/HDBSCAN |

### LLM Integration
| Library | Version | Role | Why |
|---|---|---|---|
| `litellm` | 1.40+ | Unified LLM interface | One API for OpenAI, Anthropic, Ollama, Groq |
| `anthropic` | 0.28+ | Claude SDK | Direct SDK for streaming support |

> **LLM Usage Policy (Budget-Aware):**
> - Called **once per user query** — only for final answer synthesis.
> - Context window is pre-assembled locally (max 4,000 tokens sent to LLM).
> - Default model: `claude-haiku-3-5` (cheapest, fastest Anthropic model).
> - Fallback: local `ollama` with `codellama:7b` for zero-cost offline mode.

### Persistence & State
| Library | Version | Role | Why |
|---|---|---|---|
| `sqlmodel` | 0.0.19+ | Project metadata ORM | SQLAlchemy + Pydantic in one, uses SQLite locally |
| `aiosqlite` | 0.20+ | Async SQLite driver | Non-blocking DB ops in FastAPI async context |

### Dev & Testing
| Library | Version | Role | Why |
|---|---|---|---|
| `pytest` | 8.0+ | Test runner | Industry standard |
| `pytest-asyncio` | 0.23+ | Async test support | Required for FastAPI/WebSocket tests |
| `httpx` | 0.27+ | Async HTTP test client | FastAPI's recommended test client |
| `ruff` | 0.4+ | Linter + formatter | Replaces flake8 + black + isort in one tool |
| `uv` | 0.1+ | Package manager | 10-100x faster than pip, modern lockfile support |

---

## 2. Frontend (Web UI)

### Core Framework
| Library | Version | Role | Why |
|---|---|---|---|
| `react` | 18.3+ | UI framework | Concurrent mode, stable ecosystem |
| `typescript` | 5.4+ | Type safety | Catches API contract bugs at compile time |
| `vite` | 5.2+ | Build tool | Sub-second HMR, fastest dev experience |

### State Management
| Library | Version | Role | Why |
|---|---|---|---|
| `zustand` | 4.5+ | Global state | Minimal boilerplate, no Provider hell, perfect for this scale |

> **Why not Redux?** Overkill for a single-user portfolio app.
> **Why not React Context?** Performance issues with frequent WebSocket updates.

### UI Components & Styling
| Library | Version | Role | Why |
|---|---|---|---|
| `shadcn/ui` | latest | Component library | Copy-paste components, fully customizable, Tailwind-based |
| `tailwindcss` | 3.4+ | Utility CSS | No CSS files to maintain, consistent design system |
| `lucide-react` | 0.379+ | Icon set | Clean, consistent, tree-shakeable |
| `framer-motion` | 11.0+ | Animations | Smooth panel transitions, agent step reveals |

### Data Visualization
| Library | Version | Role | Why |
|---|---|---|---|
| `@observablehq/plot` | 0.6+ | Vector scatter plot | Lightweight (vs Plotly), declarative, WebGL-ready |
| `shiki` | 1.6+ | Syntax highlighting | Accurate, VS Code grammar-based, supports 100+ languages |

> **Why Observable Plot over Plotly?**
> Plotly.js is 3MB+ bundle. Observable Plot is ~300KB and renders
> 50,000+ points smoothly with canvas/WebGL backend.

### Networking
| Library | Version | Role | Why |
|---|---|---|---|
| `@tanstack/react-query` | 5.0+ | REST data fetching | Caching, loading states, refetch on focus — all built in |
| Native `WebSocket` API | — | Streaming chat | No library needed; custom hook wraps it cleanly |

### Dev Tooling
| Library | Version | Role | Why |
|---|---|---|---|
| `eslint` | 9.0+ | Linting | Flat config format (new standard) |
| `prettier` | 3.2+ | Formatting | Consistent code style |
| `vitest` | 1.5+ | Unit testing | Vite-native, Jest-compatible API |

---

## 3. Infrastructure (Local Dev)

| Tool | Role |
|---|---|
| `docker` + `docker-compose` | One-command startup for portfolio demos |
| `make` | Task runner (`make dev`, `make test`, `make index`) |
| `sqlite` (file-based) | Project metadata persistence, zero setup |
| `chromadb` (persistent dir) | Vector store, stored in `./data/chroma/` |

---

## 4. Upgrade Path (When Budget Allows)

| Current (Free) | Upgrade To | Trigger |
|---|---|---|
| `all-MiniLM-L6-v2` (local) | `text-embedding-3-small` (OpenAI) | Accuracy complaints |
| `claude-haiku-3-5` | `claude-sonnet-4` | Complex reasoning needed |
| `chromadb` (local) | `qdrant` (self-hosted Docker) | >100k chunks |
| `sqlite` | `postgresql` | Multi-user support |
| Local `ollama` fallback | Keep as offline mode | Always useful |

---

## 5. What We Deliberately Avoided

| Rejected Tool | Reason |
|---|---|
| `LangChain` | Excessive abstraction, hidden LLM calls, hard to debug token usage |
| `LlamaIndex` | Same issue — black-box pipelines conflict with budget control |
| `Pinecone` / `Weaviate` | Cloud-only, adds cost and network dependency |
| `Redux Toolkit` | Overkill state management for this app's complexity |
| `Next.js` | SSR not needed; adds complexity without benefit for a local tool |
| `Plotly.js` | 3MB bundle, slower than Observable Plot for scatter plots |