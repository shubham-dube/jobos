"""Test configuration. Uses a dedicated Postgres database (JOBOS_TEST_DATABASE_URL)."""

from __future__ import annotations

import os
import tempfile

TEST_DB = os.environ.get("JOBOS_TEST_DATABASE_URL", "postgresql+psycopg://jobos:jobos@localhost:5432/jobos_test")
os.environ.update({
    "JOBOS_ENV": "test",
    "JOBOS_DATABASE_URL": TEST_DB,
    "JOBOS_LLM_FAKE": "1",
    "JOBOS_DATA_DIR": tempfile.mkdtemp(prefix="jobos-test-"),
    "JOBOS_API_TOKEN": "test-token",
    "JOBOS_SECRET_KEY": "test-secret-key-0123456789abcdef0123",
    "JOBOS_INTERVENTION_TIMEOUT_H": "1",
})

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS dbos CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    from jobos.db.migrate import upgrade

    upgrade(TEST_DB)


@pytest.fixture
def session():
    from jobos.db import session_scope

    with session_scope() as s:
        yield s
