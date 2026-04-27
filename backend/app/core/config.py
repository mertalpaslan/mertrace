from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent  # repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[REPO_ROOT / ".env", BASE_DIR / ".env"],  # repo root first, backend/ fallback
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Codebase Analyzer"
    version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    backend_port: int = 8000

    # LLM
    litellm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    max_context_tokens: int = 4000

    # Custom OpenAI-compatible provider
    # Set llm_api_base to your provider URL, e.g. https://api.together.xyz/v1
    # Set llm_api_key to your provider API key
    # Set litellm_model to openai/<model-name> for OpenAI-compatible APIs
    llm_api_base: str = ""   # e.g. https://api.together.xyz/v1
    llm_api_key: str = ""    # provider API key (overrides openai_api_key when set)

    # ChromaDB
    chroma_persist_dir: str = str(REPO_ROOT / "data" / "chroma")

    # Projects
    projects_tmp_dir: str = str(REPO_ROOT / "data" / "source")
    projects_data_dir: str = str(REPO_ROOT / "data" / "projects")

    # Database — default uses absolute path so it works from any cwd
    database_url: str = str(
        "sqlite+aiosqlite:///" + str(REPO_ROOT / "data" / "analyzer.db")
    )

    # Retrieval
    retrieval_top_k: int = 20
    rerank_top_k: int = 5

    # Rate limiting
    rate_limit_indexing: str = "5/minute"

    # CORS
    frontend_port: int = 5173
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @property
    def all_cors_origins(self) -> list[str]:
        """Merge configured origins with dynamic localhost:frontend_port."""
        dynamic = [
            f"http://localhost:{self.frontend_port}",
            f"http://127.0.0.1:{self.frontend_port}",
        ]
        return list(set(self.cors_origins + dynamic))

    def _abs(self, raw: str) -> Path:
        """Resolve a path relative to REPO_ROOT if not already absolute."""
        p = Path(raw)
        if not p.is_absolute():
            p = REPO_ROOT / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        return self._abs(self.chroma_persist_dir)

    @property
    def projects_data_path(self) -> Path:
        return self._abs(self.projects_data_dir)

    @property
    def projects_tmp_path(self) -> Path:
        return self._abs(self.projects_tmp_dir)

    @property
    def abs_database_url(self) -> str:
        """Return database URL with absolute path, resolving relative paths to REPO_ROOT."""
        url = self.database_url
        # Handle sqlite relative paths: sqlite+aiosqlite:///./data/... or sqlite:///data/...
        if 'sqlite' in url and ':///' in url:
            prefix, path = url.split(':///', 1)
            p = Path(path)
            if not p.is_absolute():
                p = REPO_ROOT / p
                p.parent.mkdir(parents=True, exist_ok=True)
                return f"{prefix}:///{p}"
        return url


settings = Settings()
