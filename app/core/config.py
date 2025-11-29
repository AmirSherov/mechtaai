from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    jwt_secret_key: str = Field("CHANGE_ME_SECRET", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(30, env="REFRESH_TOKEN_EXPIRE_DAYS")

    password_reset_token_expire_minutes: int = Field(
        60, env="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"
    )
    email_verification_token_expire_hours: int = Field(
        24, env="EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS"
    )

    # Celery / background jobs
    celery_broker_url: str = Field(
        "redis://localhost:6379/0",
        env="CELERY_BROKER_URL",
    )

    # SMTP / email settings (for Gmail or other SMTP providers)
    smtp_host: str = Field("smtp.gmail.com", env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_username: str = Field("", env="SMTP_USERNAME")
    smtp_password: str = Field("", env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, env="SMTP_USE_TLS")
    smtp_from_email: str = Field("", env="SMTP_FROM_EMAIL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


__all__ = ["settings", "Settings"]
