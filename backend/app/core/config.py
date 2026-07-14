from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Interview v2 API"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins_value: str = Field(
        default="http://localhost:5173,null",
        validation_alias="BACKEND_CORS_ORIGINS",
    )

    postgres_db: str = "ai_interview"
    postgres_user: str = "ai_interview"
    postgres_password: str = "ai_interview"
    postgres_host: str = "localhost"
    postgres_port: int = 55432

    jwt_secret_key: str = "change-me"
    jwt_access_token_expire_minutes: int = 1440

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5-nano"
    openai_stt_model: str = "gpt-4o-transcribe"

    redis_host: str = "localhost"
    redis_port: int = 56379
    posture_sample_fps: int = 5

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_value.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
