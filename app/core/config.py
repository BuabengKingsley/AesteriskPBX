from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Voice Transaction Support"
    app_env: str = "development"
    database_url: str = "sqlite:///./voice_support.db"
    secret_key: str = "development-only-change-me"
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 3
    session_ttl_seconds: int = 900
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

