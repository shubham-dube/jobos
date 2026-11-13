"""Programmatic Alembic entry points (used by `jobos migrate` and tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from jobos.config import get_settings

_DIR = Path(__file__).parent / "migrations"


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url or get_settings().database_url)
    return cfg


def upgrade(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


def revision(message: str, database_url: str | None = None) -> None:
    command.revision(alembic_config(database_url), message=message, autogenerate=True)
