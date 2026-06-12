"""Application configuration. Every value is overridable via environment
variables or a `.env` file — no secrets live in code."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "TenderRadar"
    environment: str = "development"
    demo_mode: bool = True

    # Database / cache
    database_url: str = (
        "postgresql+psycopg2://tenderradar:tenderradar@localhost:5432/tenderradar"
    )
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Rate limiting
    rate_limit: str = "100/minute"

    # Scraping (engine: Scrapling — free, no API keys)
    scrape_cache_ttl_seconds: int = 1800   # fetched-page cache in Redis
    respect_robots_txt: bool = True
    scrape_interval_hours: int = 6
    scrape_delay_seconds: float = 5.0
    proxy_url: str = ""
    archive_after_days: int = 180

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sendgrid_api_key: str = ""
    email_from: str = "TenderRadar <noreply@tenderradar.example>"

    # AI summaries
    ai_provider: str = "stub"  # stub | openai | groq
    openai_api_key: str = ""
    groq_api_key: str = ""

    # Storage
    storage_dir: str = "storage"
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Scheduler
    scheduler_enabled: bool = True

    # Seeded superadmin
    admin_email: str = "admin@tenderradar.example"
    admin_password: str = "Admin@12345"

    # Tier limits
    free_tier_keyword_limit: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
