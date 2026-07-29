"""Application configuration via environment variables."""
from functools import lru_cache
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    # Empty by design: startup must receive DATABASE_URL from .env or the process.
    database_url: str = Field(default="", min_length=1)

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    api_docs_enabled: bool = False
    api_trusted_hosts: str = "localhost,127.0.0.1,api"

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
    def validate_security_configuration(self) -> Self:
        username_configured = bool(self.auth_username)
        password_configured = bool(self.auth_password)
        if username_configured != password_configured:
            raise ValueError(
                "AUTH_USERNAME and AUTH_PASSWORD must both be configured or both be empty."
            )
        trusted_hosts = [
            host.strip() for host in self.api_trusted_hosts.split(",") if host.strip()
        ]
        if not trusted_hosts or "*" in trusted_hosts:
            raise ValueError(
                "API_TRUSTED_HOSTS must contain explicit host names and cannot use '*'."
            )
        self.api_trusted_hosts = ",".join(dict.fromkeys(trusted_hosts))

        cors_origins = [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]
        for origin in cors_origins:
            try:
                parsed = urlsplit(origin)
                _ = parsed.port
            except ValueError as exc:
                raise ValueError(
                    "CORS_ALLOW_ORIGINS must contain valid HTTP(S) origins."
                ) from exc
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ALLOW_ORIGINS must contain explicit HTTP(S) origins "
                    "without paths, credentials, queries or fragments."
                )
        self.cors_allow_origins = ",".join(dict.fromkeys(cors_origins))
        return self

    @property
    def trusted_hosts(self) -> list[str]:
        return self.api_trusted_hosts.split(",")

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin
            for origin in self.cors_allow_origins.split(",")
            if origin
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
