"""Application configuration via environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://finance:finance@localhost:5432/finance"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # LLM / Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"
    ollama_timeout_s: float = 60.0
    ollama_num_ctx: int = 2048
    ollama_num_predict: int = 256
    llm_enabled: bool = True
    llm_fallback_enabled: bool = False

    # Auth (BasicAuth, single user). Auth is OFF when both vars are empty.
    auth_username: str = ""
    auth_password: str = ""

    # CORS / rate limiting
    cors_allow_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = 120


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
