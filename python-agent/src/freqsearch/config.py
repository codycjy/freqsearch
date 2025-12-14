"""Configuration management for FreqSearch Agent."""

from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    env: Environment = Environment.DEVELOPMENT

    # gRPC connection to Go backend
    grpc_server: str = Field(default="localhost:50051", description="Go backend gRPC address")
    grpc_timeout: int = Field(default=30, description="gRPC call timeout in seconds")

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://freqsearch:freqsearch_dev@localhost:5672/",
        description="RabbitMQ connection URL",
    )

    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI, description="LLM provider to use")
    llm_model: Optional[str] = Field(
        default=None, description="Model ID (uses provider default if not set)"
    )
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, gt=0)

    # Provider-specific API keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    ollama_url: str = Field(default="http://localhost:11434", description="Ollama server URL")

    # Optimization defaults
    default_max_iterations: int = Field(default=10, description="Default max optimization iterations")
    default_min_sharpe: float = Field(default=1.0, description="Default minimum Sharpe ratio")
    default_min_profit_pct: float = Field(default=10.0, description="Default minimum profit %")
    default_max_drawdown_pct: float = Field(default=20.0, description="Default maximum drawdown %")
    default_min_trades: int = Field(default=50, description="Default minimum trades")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_json: bool = Field(default=False, description="Output logs as JSON")

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.env == Environment.DEVELOPMENT


# Global settings instance
settings = Settings()
