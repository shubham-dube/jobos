from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (prefix JOBOS_) or .env."""

    model_config = SettingsConfigDict(env_prefix="JOBOS_", env_file=".env", extra="ignore")

    env: str = "dev"  # dev | test | prod
    database_url: str = "postgresql+psycopg://jobos:jobos@localhost:5432/jobos"
    data_dir: Path = Path("./data")  # documents, screenshots, evidence (S3 later)
    public_base_url: str = "http://localhost:8000"  # where webhooks reach the API
    web_base_url: str = "http://localhost:3000"  # dashboard links in notifications

    # auth (ADR-0013)
    api_token: str = "dev-api-token-change-me"
    secret_key: str = "dev-secret-key-change-me-32-bytes-min!!"  # encrypts stored secrets

    # LLM (ADR-0011)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_default_route: str = "openrouter:anthropic/claude-sonnet-5.5"
    llm_routes: dict[str, str] = Field(default_factory=dict)  # task -> "provider:model"
    llm_daily_budget_usd: float = 5.0
    llm_fake: bool = False  # use the deterministic fake provider (tests / offline dev)

    # workflows
    worker_role: str = "all"  # api | worker | all
    apply_concurrency: int = 2  # applications running at once per worker (≈ runner tabs)
    runner_task_timeout_s: int = 300
    intervention_timeout_h: float = 48.0

    # notifications (ADR-0012)
    resend_api_key: str = ""
    email_from: str = ""  # e.g. "JobOS <jobs@yourdomain.com>"
    notify_email_to: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_to: str = ""  # E.164 without "+", e.g. 9198xxxxxxx
    whatsapp_verify_token: str = "jobos-verify"
    whatsapp_app_secret: str = ""  # verifies webhook signatures
    whatsapp_template: str = ""  # approved template name for messages outside the 24h window

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
