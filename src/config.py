"""
Configuration settings for Project Atlas.
Loads settings from environment variables and .env file.
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    API_KEY: str = "atlas-secret-key-2025"

    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "project_atlas"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root_password_2025"

    # Read-only MySQL User (Enforces database safety)
    MYSQL_READONLY_USER: str = "atlas_readonly"
    MYSQL_READONLY_PASSWORD: str = "AtlasReadOnly_Pass2025!"

    # LLM Settings
    LLM_PROVIDER: str = "deterministic"  # 'deterministic', 'openai', 'gemini', 'anthropic', 'groq', 'ollama'
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Vector DB & Storage
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Guardrails & Operational Constraints
    CONFIDENCE_THRESHOLD: float = 0.70
    MAX_SQL_ROWS: int = 50
    SQL_QUERY_TIMEOUT_SECONDS: float = 5.0
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    ENABLE_SEMANTIC_CACHE: bool = True


settings = Settings()
