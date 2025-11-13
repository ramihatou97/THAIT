"""
NeuroscribeAI Configuration Management
Handles all application settings using Pydantic Settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    """Application settings with validation"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True
    )

    # Environment
    environment: str = Field(default="development", pattern="^(development|production|test)$")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # API Server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_workers: int = Field(default=4, ge=1, le=32)
    api_reload: bool = Field(default=True)

    # Database
    database_url: str = Field(
        default="postgresql://neuroscribe:neuroscribe_pass@localhost:5432/neuroscribe"
    )
    database_pool_size: int = Field(default=20, ge=5, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout: int = Field(default=30, ge=10, le=60)
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_max_connections: int = Field(default=50, ge=10, le=200)

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="neo4j_password")
    neo4j_database: str = Field(default="neo4j")

    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4-turbo-preview")
    openai_max_tokens: int = Field(default=4000, ge=100, le=8000)
    openai_temperature: float = Field(default=0.3, ge=0.0, le=2.0)

    anthropic_api_key: Optional[str] = Field(default=None)
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    anthropic_max_tokens: int = Field(default=4000, ge=100, le=8000)
    anthropic_temperature: float = Field(default=0.3, ge=0.0, le=1.0)

    llm_provider: str = Field(default="anthropic", pattern="^(openai|anthropic)$")
    llm_fallback_provider: Optional[str] = Field(default="openai")
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_timeout: int = Field(default=120, ge=30, le=300)

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")
    celery_task_always_eager: bool = Field(default=False)
    worker_concurrency: int = Field(default=4, ge=1, le=16)
    worker_prefetch_multiplier: int = Field(default=2, ge=1, le=10)
    task_time_limit: int = Field(default=600, ge=60, le=1800)
    task_soft_time_limit: int = Field(default=540, ge=50, le=1700)

    # Feature Flags
    enable_nli_verification: bool = Field(default=True)
    enable_clinical_rules: bool = Field(default=True)
    enable_validation: bool = Field(default=True)
    enable_graph_construction: bool = Field(default=True)
    enable_ml_learning: bool = Field(default=False)

    # Extraction
    extraction_timeout: int = Field(default=300, ge=60, le=600)
    extraction_batch_size: int = Field(default=10, ge=1, le=100)
    extraction_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    extraction_use_ner: bool = Field(default=True)
    extraction_use_llm: bool = Field(default=True)

    # Temporal Reasoning
    temporal_conflict_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    temporal_max_pod: int = Field(default=100, ge=30, le=365)

    # Validation
    validation_score_threshold: int = Field(default=85, ge=0, le=100)
    validation_completeness_threshold: int = Field(default=90, ge=0, le=100)
    validation_accuracy_threshold: int = Field(default=95, ge=0, le=100)
    validation_enable_nli: bool = Field(default=True)

    # Clinical Rules
    rules_enable_all: bool = Field(default=True)
    rules_seizure_prophylaxis: bool = Field(default=True)
    rules_dvt_prophylaxis: bool = Field(default=True)
    rules_steroid_taper: bool = Field(default=True)
    rules_sodium_monitoring: bool = Field(default=True)
    rules_hemorrhage_risk: bool = Field(default=True)
    rules_discharge_readiness: bool = Field(default=True)

    # Performance
    vector_search_top_k: int = Field(default=10, ge=1, le=50)
    vector_similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    cache_ttl: int = Field(default=3600, ge=0, le=86400)
    cache_max_size: int = Field(default=1000, ge=100, le=10000)

    # Security
    api_key_header: str = Field(default="X-API-Key")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )
    cors_allow_credentials: bool = Field(default=True)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60, ge=10, le=1000)

    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None)
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)

    # Backup
    backup_enabled: bool = Field(default=True)
    backup_schedule: str = Field(default="0 2 * * *")
    backup_retention_days: int = Field(default=30, ge=1, le=365)
    backup_s3_bucket: Optional[str] = Field(default=None)

    # Testing
    pytest_markers: str = Field(default="unit,integration,performance")
    test_database_url: Optional[str] = Field(default=None)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is secure in production"""
        if v == "change-me-in-production-use-python-secrets-token-urlsafe":
            import os
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError("Must set a secure SECRET_KEY in production!")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("llm_fallback_provider")
    @classmethod
    def validate_llm_fallback_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate LLM fallback provider if provided"""
        if v is not None and v not in ["openai", "anthropic"]:
            raise ValueError("llm_fallback_provider must be either 'openai' or 'anthropic'")
        return v

    @model_validator(mode="after")
    def validate_llm_config(self) -> "Settings":
        """Validate LLM configuration after all fields are set"""
        # Only validate in production, allow development without API keys
        if self.environment == "production":
            if self.llm_provider == "openai" and not self.openai_api_key:
                raise ValueError("OpenAI API key required when using OpenAI provider in production")
            if self.llm_provider == "anthropic" and not self.anthropic_api_key:
                raise ValueError("Anthropic API key required when using Anthropic provider in production")
        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        """Check if running in test"""
        return self.environment == "test"

    def get_database_url(self, for_alembic: bool = False) -> str:
        """Get database URL, optionally for Alembic migrations"""
        if for_alembic:
            # Alembic needs postgresql:// not postgresql+asyncpg://
            return self.database_url.replace("+asyncpg", "")
        return self.database_url


# Global settings instance
# LLM validation happens automatically during initialization via model_validator
settings = Settings()
