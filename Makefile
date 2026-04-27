.PHONY: install dev dev-backend dev-frontend test test-cov lint format format-check clean init-dirs help

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKEND_DIR  := backend
FRONTEND_DIR := frontend

# ── Ports (override via env or .env file) ─────────────────────────────────────
-include .env
BACKEND_PORT ?= 8000
VITE_PORT    ?= 5173

# ── Install ───────────────────────────────────────────────────────────────────
install:
	@echo ">>> Installing backend dependencies..."
	cd $(BACKEND_DIR) && uv sync --all-extras
	@echo ">>> Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install
	@echo ">>> Done."

# ── Dev servers ───────────────────────────────────────────────────────────────
dev-backend:
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-frontend:
	cd $(FRONTEND_DIR) && VITE_PORT=$(VITE_PORT) VITE_BACKEND_PORT=$(BACKEND_PORT) npm run dev

dev:
	@echo ">>> Starting backend (:$(BACKEND_PORT)) + frontend (:$(VITE_PORT))..."
	$(MAKE) dev-backend & $(MAKE) dev-frontend

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	cd $(BACKEND_DIR) && uv run pytest tests/ -v

test-cov:
	cd $(BACKEND_DIR) && uv run pytest tests/ -v --cov=app --cov-report=term-missing

# ── Linting & formatting ──────────────────────────────────────────────────────
lint:
	cd $(BACKEND_DIR) && uv run ruff check app/ tests/

format:
	cd $(BACKEND_DIR) && uv run ruff format app/ tests/

format-check:
	cd $(BACKEND_DIR) && uv run ruff format --check app/ tests/

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	@echo ">>> Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo ">>> Done."

# ── Data dirs ─────────────────────────────────────────────────────────────────
init-dirs:
	mkdir -p data/chroma data/projects logs
	@echo ">>> Data directories created."

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker compose up --build

docker-down:
	docker compose down

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Codebase Analyzer — Available Commands"
	@echo "  ───────────────────────────────────────"
	@echo "  make install      Install all backend + frontend deps"
	@echo "  make dev          Start backend (:$(BACKEND_PORT)) + frontend (:$(VITE_PORT))"
	@echo "  make test         Run backend test suite"
	@echo "  make test-cov     Run tests with coverage report"
	@echo "  make lint         Ruff lint check"
	@echo "  make format       Ruff auto-format"
	@echo "  make clean        Remove build artifacts"
	@echo "  make docker-up    Build and start Docker stack"
	@echo "  make init-dirs    Create data/ and logs/ directories"
	@echo ""
