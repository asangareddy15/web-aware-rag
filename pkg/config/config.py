from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "Web-Aware RAG Engine"

    # Legacy Gemini configuration (optional)
    gemini_api_key: str | None = Field(None, description="Gemini API key (legacy, optional)")

    # Voyage API Configuration
    voyage_api_key: str = Field(..., validation_alias="VOYAGE_API_KEY", description="VoyageAI API key for contextualized embeddings")

    # PostgreSQL Configuration
    postgres_db_user: str = Field(..., description="PostgreSQL username")
    postgres_db_password: str = Field(..., description="PostgreSQL password")
    postgres_db_host: str = Field(..., description="PostgreSQL host")
    postgres_db_port: int = Field(..., description="PostgreSQL port")
    postgres_db_name: str = Field(..., description="PostgreSQL database name")

    # Redis Configuration
    redis_host: str = Field(..., description="Redis host")
    redis_port: int = Field(..., description="Redis port")
    redis_db: int = Field(0, description="Redis database index for queues")
    redis_queue_name: str = Field("url_ingestion", description="Redis list name used for ingestion jobs")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
