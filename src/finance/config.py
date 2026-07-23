"""Application configuration via environment variables."""
from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
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
    ollama_timeout_s: float = Field(default=60.0, gt=0)
    ollama_num_ctx: int = Field(default=2048, gt=0)
    ollama_num_predict: int = Field(default=256, gt=0)
    llm_enabled: bool = True
    llm_fallback_enabled: bool = False

    # Auth (BasicAuth, single user). Auth is OFF when both vars are empty.
    auth_username: str = ""
    auth_password: str = ""

    # Optional local privacy lock. Enable Secure cookies behind HTTPS.
    app_lock_cookie_secure: bool = False

    # CORS / rate limiting
    cors_allow_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = Field(default=120, ge=0)

    @model_validator(mode="after")
    def validate_basic_auth_pair(self) -> Self:
        username_configured = bool(self.auth_username)
        password_configured = bool(self.auth_password)
        if username_configured != password_configured:
            raise ValueError(
                "AUTH_USERNAME and AUTH_PASSWORD must both be configured or both be empty."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
