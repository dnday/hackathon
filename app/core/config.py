from __future__ import annotations
from typing import Optional
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KosCheck API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL")
    cron_api_key: Optional[str] = Field(default=None, alias="CRON_API_KEY")

    firebase_credentials_path: Optional[str] = Field(
        default=None, alias="FIREBASE_CREDENTIALS_PATH"
    )
    firestore_history_collection: str = "validation_history"
    firestore_benchmark_collection: str = "market_benchmarks"

    cors_origins: list[str] = ["*"]
    max_chat_chars: int = 60_000
    max_images: int = 8
    max_image_bytes: int = 8_000_000
    scraper_timeout_seconds: float = 20.0
    scraper_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 KosCheckBot/1.0"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def resolved_gemini_api_key(self) -> Optional[str]:
        return self.google_api_key or self.gemini_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
