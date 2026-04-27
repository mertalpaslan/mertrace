from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
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
    litellm_model: str = "claude-haiku-3-5"
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
    chroma_persist_dir: str = str(BASE_DIR.parent / "data" / "chroma")

    # Projects
    projects_tmp_dir: str = str(BASE_DIR.parent / "data" / "source")
    projects_data_dir: str = str(BASE_DIR.parent / "data" / "projects")

    # Database
    database_url: str = str(
        "sqlite+aiosqlite:///" + str(BASE_DIR.parent / "data" / "analyzer.db")
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

    @property
    def chroma_path(self) -> Path:
        p = Path(self.chroma_persist_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def projects_data_path(self) -> Path:
        p = Path(self.projects_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def projects_tmp_path(self) -> Path:
        p = Path(self.projects_tmp_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
