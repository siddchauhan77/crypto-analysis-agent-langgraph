"""Secret-safe application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load required credentials and bounded runtime defaults from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        populate_by_name=True,
    )

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    freecrypto_api_key: SecretStr = Field(alias="FREECRYPTO_API_KEY")
    news_api_key: SecretStr = Field(alias="NEWS_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    request_timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        alias="REQUEST_TIMEOUT_SECONDS",
    )
    max_http_retries: int = Field(default=2, ge=0, le=3, alias="MAX_HTTP_RETRIES")
    checkpoint_db_path: Path = Field(
        default=Path(".data/crypto-agent.sqlite3"),
        alias="CHECKPOINT_DB_PATH",
    )
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: SecretStr | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="crypto-analysis-agent",
        alias="LANGSMITH_PROJECT",
    )

    @field_validator("openai_api_key", "freecrypto_api_key", "news_api_key")
    @classmethod
    def reject_placeholder_secrets(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().strip()
        placeholders = ("your_", "replace_", "example", "changeme")
        if not secret or secret.lower().startswith(placeholders):
            raise ValueError("A real API credential is required")
        return SecretStr(secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()
