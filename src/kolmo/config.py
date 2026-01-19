"""
KOLMO Configuration Management

🔒 REQ-7.1: API keys and credentials MUST be stored in external secret management.
🔒 REQ-7.3: Repository MUST include .env.example with placeholder values.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # === External Provider Configuration ===
    frankfurter_base_url: str = Field(
        default="https://api.frankfurter.dev",
        description="Frankfurter API base URL (primary provider)"
    )
    cbr_base_url: str = Field(
        default="https://www.cbr.ru/scripts/XML_dynamic.asp",
        description="Central Bank of Russia API base URL (fallback 1)"
    )
    twelvedata_api_key: str = Field(
        default="",
        description="TwelveData API key (fallback 2)"
    )
    twelvedata_base_url: str = Field(
        default="https://api.twelvedata.com",
        description="TwelveData API base URL"
    )
    
    # === Database Configuration ===
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    database_name: str = Field(default="kolmo_db")
    database_user: str = Field(default="kolmo_user")
    database_password: str = Field(default="")
    database_ssl_mode: str = Field(default="prefer")
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            f"?sslmode={self.database_ssl_mode}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Construct asyncpg connection URL."""
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )
    
    # === API Configuration ===
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_secret_key: str = Field(default="")
    
    # === Scheduler Configuration ===
    scheduler_cron_hour: int = Field(default=22, description="Daily job hour (EST)")
    scheduler_cron_minute: int = Field(default=0, description="Daily job minute")
    scheduler_timezone: str = Field(default="US/Eastern")
    
    # === Logging ===
    log_level: str = Field(default="INFO")
    sentry_dsn: str = Field(default="")
    
    # === Feature Flags ===
    enable_backfill: bool = Field(default=False)
    
    # === JSON Export Configuration ===
    json_export_enabled: bool = Field(
        default=True,
        description="Enable automatic JSON export after computation"
    )
    json_export_dir: str = Field(
        default="./data/export",
        description="Directory for JSON export files"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
