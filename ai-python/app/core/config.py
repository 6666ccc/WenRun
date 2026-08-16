from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_chat_model: str
    embedding_model: str
    qdrant_url: str = "http://localhost:6333"
    hospital_collection: str = Field(
        "wenrun_hospital_custom",
        validation_alias="QDRANT_HOSPITAL_COLLECTION",
    )
    medical_collection: str = Field(
        "wenrun_medical_general",
        validation_alias="QDRANT_MEDICAL_COLLECTION",
    )
    memory_collection: str = Field(
        "wenrun_conversation_memory",
        validation_alias="QDRANT_MEMORY_COLLECTION",
    )
    checkpoint_path: str = Field(
        "./data/checkpoints.sqlite",
        validation_alias="AI_CHECKPOINT_PATH",
    )
    java_base_url: str = Field(
        "http://localhost:8080",
        validation_alias="AI_JAVA_BASE_URL",
    )
    internal_api_key: str = Field(
        validation_alias=AliasChoices("AI_INTERNAL_API_KEY", "AI_SERVICE_API_KEY"),
    )
    short_term_token_budget: int = 6000
    agent_max_steps: int = 8
    rag_min_score: float = Field(0.3, validation_alias="AI_RAG_MIN_SCORE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
