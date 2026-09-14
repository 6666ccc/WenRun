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
    intent_lightweight_enabled: bool = Field(
        True,
        validation_alias="INTENT_LIGHTWEIGHT_ENABLED",
    )
    context_total_tokens: int = Field(8_000, ge=1_000, validation_alias="AI_CONTEXT_TOTAL_TOKENS")
    context_system_tokens: int = Field(2_000, ge=500, validation_alias="AI_CONTEXT_SYSTEM_TOKENS")
    context_summary_tokens: int = Field(1_200, ge=200, validation_alias="AI_CONTEXT_SUMMARY_TOKENS")
    context_recent_tokens: int = Field(2_400, ge=400, validation_alias="AI_CONTEXT_RECENT_TOKENS")
    context_external_tokens: int = Field(2_400, ge=400, validation_alias="AI_CONTEXT_EXTERNAL_TOKENS")
    rag_metadata_mysql_host: str = Field("", validation_alias="RAG_METADATA_MYSQL_HOST")
    rag_metadata_mysql_port: int = Field(3306, ge=1, le=65535, validation_alias="RAG_METADATA_MYSQL_PORT")
    rag_metadata_mysql_database: str = Field("wenrun", validation_alias="RAG_METADATA_MYSQL_DATABASE")
    rag_metadata_mysql_user: str = Field("", validation_alias="RAG_METADATA_MYSQL_USER")
    rag_metadata_mysql_password: str = Field("", validation_alias="RAG_METADATA_MYSQL_PASSWORD")
    summary_trigger_tokens: int = Field(5_000, ge=500, validation_alias="AI_SUMMARY_TRIGGER_TOKENS")
    summary_message_limit: int = Field(12, ge=10, validation_alias="AI_SUMMARY_MESSAGE_LIMIT")
    intent_label_threshold: float = Field(
        0.50,
        ge=0.0,
        le=1.0,
        validation_alias="INTENT_LABEL_THRESHOLD",
    )
    intent_acceptance_threshold: float = Field(
        0.60,
        ge=0.0,
        le=1.0,
        validation_alias="INTENT_ACCEPTANCE_THRESHOLD",
    )
    intent_ambiguity_margin: float = Field(
        0.12,
        ge=0.0,
        le=1.0,
        validation_alias="INTENT_AMBIGUITY_MARGIN",
    )
    intent_ood_similarity_threshold: float = Field(
        0.08,
        ge=0.0,
        le=1.0,
        validation_alias="INTENT_OOD_SIMILARITY_THRESHOLD",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
