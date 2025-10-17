from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "Web-Aware RAG Engine"

    # Gemini API Configuration
    gemini_api_key: str = Field(..., description="Gemini API key for LLM and embeddings")

    # PostgreSQL Configuration
    postgres_db_user: str = Field(..., description="PostgreSQL username")
    postgres_db_password: str = Field(..., description="PostgreSQL password")
    postgres_db_host: str = Field(..., description="PostgreSQL host")
    postgres_db_port: int = Field(..., description="PostgreSQL port")
    postgres_db_name: str = Field(..., description="PostgreSQL database name")

    # Redis Configuration
    redis_host: str = Field(..., description="Redis host")
    redis_port: int = Field(..., description="Redis port")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
