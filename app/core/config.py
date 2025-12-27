from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    jwt_secret_key: str = Field("CHANGE_ME_SECRET", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(30, env="REFRESH_TOKEN_EXPIRE_DAYS")
    bot_secret_key: str = Field("", env="BOT_SECRET_KEY")

    password_reset_token_expire_minutes: int = Field(
        60, env="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"
    )
    email_verification_token_expire_hours: int = Field(
        24, env="EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS"
    )
    celery_broker_url: str = Field(
        "redis://localhost:6379/0",
        env="CELERY_BROKER_URL",
    )
    ai_proxy_url: str = Field(
        "http://localhost:8787/v1/chat",
        env="AI_PROXY_URL",
    )
    ai_proxy_timeout_seconds: int = Field(
        60,
        env="AI_PROXY_TIMEOUT_SECONDS",
    )
    ai_proxy_model: str = Field(
        "gpt-4o-mini",
        env="AI_PROXY_MODEL",
    )
    wants_ai_system_prompt_path: str = Field(
        "app/core/wants/prompts/diagnose_wants_system.txt",
        env="WANTS_AI_SYSTEM_PROMPT_PATH",
    )
    future_story_system_prompt_path: str = Field(
        "app/core/future_story/prompts/build_future_story_system.txt",
        env="FUTURE_STORY_SYSTEM_PROMPT_PATH",
    )
    generate_goals_system_prompt_path: str = Field(
        "app/core/generate_goals/prompts/generate_goals_system.txt",
        env="GENERATE_GOALS_SYSTEM_PROMPT_PATH",
    )
    plan_steps_system_prompt_path: str = Field(
        "app/core/plan_steps/prompts/plan_steps_system.txt",
        env="PLAN_STEPS_SYSTEM_PROMPT_PATH",
    )
    weekly_review_system_prompt_path: str = Field(
        "app/core/rituals/prompts/weekly_review_system.txt",
        env="WEEKLY_REVIEW_SYSTEM_PROMPT_PATH",
    )
    ai_proxy_image_url: str = Field(
        "http://localhost:8787/v1/images",
        env="AI_PROXY_IMAGE_URL",
    )
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
