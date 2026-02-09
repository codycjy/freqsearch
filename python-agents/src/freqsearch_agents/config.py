"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMModelSettings(BaseSettings):
    """Per-agent LLM model configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API keys
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openrouter_api_key: str = Field("", alias="OPENROUTER_API_KEY")

    # Default model (fallback)
    default_model: str = Field("google/gemini-3-pro-preview", alias="LLM_DEFAULT_MODEL")

    # Per-agent model configuration
    scout_model: str = Field("google/gemini-3-flash-preview", alias="LLM_SCOUT_MODEL")
    engineer_model: str = Field("google/gemini-3-pro-preview", alias="LLM_ENGINEER_MODEL")
    analyst_model: str = Field("google/gemini-3-pro-preview", alias="LLM_ANALYST_MODEL")

    # Model parameters
    temperature: float = Field(0.1, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(4096, alias="LLM_MAX_TOKENS")

    # Embedding model (OpenAI)
    embedding_model: str = Field("text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")


class OpenAISettings(BaseSettings):
    """OpenAI API configuration (legacy, for embeddings)."""

    api_key: str = Field(..., alias="OPENAI_API_KEY")
    model: str = Field("gpt-4-turbo-preview", alias="OPENAI_MODEL")
    embedding_model: str = Field("text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    temperature: float = 0.1
    max_tokens: int = 4096


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    url: str = Field(
        "postgresql+asyncpg://freqsearch:freqsearch@localhost:5432/freqsearch",
        alias="DATABASE_URL",
    )
    pool_size: int = 5
    max_overflow: int = 10


class RabbitMQSettings(BaseSettings):
    """RabbitMQ configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = Field("amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    exchange_name: str = "freqsearch.events"
    exchange_type: str = "topic"
    prefetch_count: int = 10


class GRPCSettings(BaseSettings):
    """gRPC client configuration."""

    go_backend_addr: str = Field("localhost:50051", alias="GO_BACKEND_GRPC_ADDR")
    timeout_seconds: int = 30


class FactorSettings(BaseSettings):
    """Factor API configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_url: str = Field("http://localhost:8083/api/v1", alias="FACTOR_API_URL")
    timeout_seconds: int = 30


class ScoutSettings(BaseSettings):
    """Scout Agent configuration."""

    cron_schedule: str = Field("0 */6 * * *", alias="SCOUT_CRON_SCHEDULE")
    max_strategies_per_run: int = Field(50, alias="SCOUT_MAX_STRATEGIES_PER_RUN")
    similarity_threshold: int = 3  # Hamming distance for SimHash


class EngineerSettings(BaseSettings):
    """Engineer Agent configuration."""

    max_retries: int = Field(3, alias="ENGINEER_MAX_RETRIES")
    code_validation_timeout: int = 30


class AnalystSettings(BaseSettings):
    """Analyst Agent configuration."""

    confidence_threshold: float = Field(0.7, alias="ANALYST_CONFIDENCE_THRESHOLD")
    min_trades_for_analysis: int = 10
    min_profit_for_approval: float = 0.0


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", alias="LOG_LEVEL")
    format: Literal["json", "console"] = Field("json", alias="LOG_FORMAT")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-settings
    llm: LLMModelSettings = Field(default_factory=LLMModelSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    grpc: GRPCSettings = Field(default_factory=GRPCSettings)
    factor: FactorSettings = Field(default_factory=FactorSettings)
    scout: ScoutSettings = Field(default_factory=ScoutSettings)
    engineer: EngineerSettings = Field(default_factory=EngineerSettings)
    analyst: AnalystSettings = Field(default_factory=AnalystSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
