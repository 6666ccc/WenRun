from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    internal_api_key: str = Field(
        "",
        validation_alias=AliasChoices("AI_INTERNAL_API_KEY", "AI_SERVICE_API_KEY"),
    )
    tavily_api_key: str = Field("", validation_alias="TAVILY_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
