from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://fisiobot:fisiobot_dev@localhost:5432/fisiobot"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    ENCRYPTION_KEY: str = ""
    SECRET_KEY: str = ""

    # Meta WhatsApp
    META_APP_SECRET: str = ""

    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Google OAuth2 (app-level, para refresh de tokens)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # App
    BASE_URL: str = "http://localhost:8000"

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
