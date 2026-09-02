from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    internal_api_key: str = Field(
        "",
        validation_alias=AliasChoices("AI_INTERNAL_API_KEY", "AI_SERVICE_API_KEY"),
    )
    delegation_signing_secret: str = Field(
        "",
        validation_alias=AliasChoices(
            "AI_DELEGATION_VERIFYING_SECRET",
            "AI_DELEGATION_SIGNING_SECRET",
        ),
    )
    java_tool_base_url: str = Field(
        "http://localhost:8080",
        validation_alias="JAVA_TOOL_BASE_URL",
    )
    java_tool_timeout_seconds: float = Field(
        5.0,
        validation_alias="JAVA_TOOL_TIMEOUT_SECONDS",
    )
    redis_url: str = Field("", validation_alias="AI_REDIS_URL")
    checkpoint_ttl_minutes: int = Field(
        1440,
        validation_alias="AI_CHECKPOINT_TTL_MINUTES",
    )
    tavily_api_key: str = Field("", validation_alias="TAVILY_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
