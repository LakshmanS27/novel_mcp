from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DLP_MCP_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Risk-Aware MCP DLP"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    default_tree_depth: int = 3
    max_tree_depth: int = 8
    stat_concurrency: int = 64
    similarity_bucket_limit: int = 64
    scan_percent: float = 0.05
    max_scan_percent: float = 0.05
    min_scan_percent: float = 0.01
    db_path: Path = Field(default=BASE_DIR / "mcp_server" / "data" / "state.db")
    prompts_dir: Path = Field(default=BASE_DIR / "mcp_server" / "prompts")
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str | None = None
    llm_model: str = "local-model"
    llm_timeout_seconds: float = 30.0
    llm_enabled: bool = True
    max_file_read_bytes: int = 2_000_000
    scan_chunk_size: int = 8192
    default_candidate_mode: str = "broad"
    max_candidate_files: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
