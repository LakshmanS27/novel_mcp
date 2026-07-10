from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_server.utils.llm import normalize_openai_base_url


BASE_DIR = Path(__file__).resolve().parents[2]

# Provider constants
OPENROUTER = "openrouter"
OPENAI = "openai"
COMMANDCODE = "commandcode"

# Default provider configurations
PROVIDER_CONFIGS = {
    OPENROUTER: {
        "base_url_env": "OPENROUTER_BASE_URL",
        "api_key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "nvidia/nemotron-3-nano-30b-a3b:free",
    },
    OPENAI: {
        "base_url_env": "OPENAI_BASE_URL",
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    COMMANDCODE: {
        "base_url_env": "COMMANDCODE_BASE_URL",
        "api_key_env": "COMMANDCODE_API_KEY",
        "model_env": "COMMANDCODE_MODEL",
        "default_base_url": "https://api.commandcode.ai/provider/v1",
        "default_model": "commandcode-v1",
    },
}


def detect_provider() -> str:
    """Detect which LLM provider to use based on available API keys.

    Priority: CommandCode > OpenAI > OpenRouter (first with valid key wins).

    Shared by the server (this module) and `mcp_client/chat_client.py` so the
    two never drift on provider defaults or detection order.
    """
    for provider in [COMMANDCODE, OPENAI, OPENROUTER]:
        config = PROVIDER_CONFIGS[provider]
        api_key = os.environ.get(config["api_key_env"], "").strip()
        if api_key and api_key not in ("", "your-api-key-here", "sk-xxx"):
            return provider
    return OPENROUTER  # Default fallback


def get_provider_env_vars(provider: str) -> dict[str, str]:
    """Get resolved environment variables for a provider."""
    config = PROVIDER_CONFIGS[provider]
    return {
        "base_url": normalize_openai_base_url(
            os.environ.get(config["base_url_env"], config["default_base_url"])
        ),
        "api_key": os.environ.get(config["api_key_env"], ""),
        "model": os.environ.get(config["model_env"], config["default_model"]),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DLP_MCP_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Risk-Aware MCP DLP"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    default_tree_depth: int = 3
    max_tree_depth: int = 8
    stat_concurrency: int = 64
    similarity_bucket_limit: int = 64
    max_scan_percent: float = 0.05
    min_scan_percent: float = 0.01
    db_path: Path = Field(default=BASE_DIR / "mcp_server" / "data" / "state.db")
    prompts_dir: Path = Field(default=BASE_DIR / "mcp_server" / "prompts")

    # Legacy OpenRouter support (for backward compatibility)
    openrouter_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_BASE_URL"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY"),
    )
    openrouter_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_MODEL"),
    )

    # Multi-provider support
    llm_provider: str = Field(default="", description="Auto-detected provider: openrouter, openai, commandcode")
    llm_base_url: str = Field(default="", description="LLM API base URL")
    llm_api_key: str | None = Field(default=None, description="LLM API key")
    llm_model: str = Field(default="", description="LLM model name")
    llm_timeout_seconds: float = 30.0
    llm_enabled: bool = True
    max_file_read_bytes: int = 2_000_000
    scan_chunk_size: int = 8192
    default_candidate_mode: str = "broad"
    max_candidate_files: int = 100

    @model_validator(mode="after")
    def apply_llm_fallbacks(self) -> "Settings":
        # First, detect the provider based on available API keys
        detected_provider = detect_provider()
        
        # If explicit DLP_MCP_LLM_* settings are provided, use those
        has_explicit_url = self.llm_base_url not in ("", "http://127.0.0.1:11434/v1")
        has_explicit_key = self.llm_api_key not in (None, "")
        has_explicit_model = self.llm_model not in ("", "local-model")
        
        if has_explicit_url and has_explicit_key and has_explicit_model:
            # User explicitly configured everything, keep as-is
            self.llm_base_url = normalize_openai_base_url(self.llm_base_url)
            self.llm_provider = detected_provider
            return self
        
        # Otherwise, auto-configure from detected provider
        provider_env = get_provider_env_vars(detected_provider)
        
        # Apply provider settings if not explicitly overridden
        if not has_explicit_url:
            self.llm_base_url = provider_env["base_url"]
        if not has_explicit_key:
            self.llm_api_key = provider_env["api_key"]
        if not has_explicit_model:
            self.llm_model = provider_env["model"]
        
        self.llm_provider = detected_provider
        
        # Legacy OpenRouter fallback for backward compatibility
        if not self.llm_api_key and self.openrouter_api_key:
            self.llm_api_key = self.openrouter_api_key
        if not self.llm_base_url and self.openrouter_base_url:
            self.llm_base_url = normalize_openai_base_url(self.openrouter_base_url)
        if not self.llm_model and self.openrouter_model:
            self.llm_model = self.openrouter_model
            self.llm_provider = OPENROUTER

        if self.llm_base_url:
            self.llm_base_url = normalize_openai_base_url(self.llm_base_url)
        
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
