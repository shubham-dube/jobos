"""DBOS runtime wiring (ADR-0010)."""

from __future__ import annotations

from functools import lru_cache

from dbos import DBOS, DBOSClient, DBOSConfig

from jobos.config import get_settings

APPLY_QUEUE = "apply"  # partitioned by company: at most one running application per employer
DISCOVERY_QUEUE = "discovery"
_dbos: DBOS | None = None


def system_db_url() -> str:
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


def launch(run_schedules: bool = True) -> DBOS:
    """Start DBOS in this process (worker role)."""
    global _dbos
    if _dbos is not None:
        return _dbos
    # import modules so their workflows/steps register before launch
    from . import application, discovery, inbox  # noqa: F401

    config: DBOSConfig = {"name": "jobos", "system_database_url": system_db_url(), "log_level": "INFO"}
    _dbos = DBOS(config=config)
    DBOS.launch()
    DBOS.register_queue(APPLY_QUEUE, worker_concurrency=get_settings().apply_concurrency, partition_concurrency=1)
    DBOS.register_queue(DISCOVERY_QUEUE, worker_concurrency=1)
    if run_schedules:
        from .discovery import discovery_tick
        from .inbox import inbox_tick

        DBOS.apply_schedules([
            {"schedule_name": "discovery-tick", "workflow_fn": discovery_tick, "schedule": "*/15 * * * *"},
            {"schedule_name": "inbox-tick", "workflow_fn": inbox_tick, "schedule": "*/5 * * * *"},
        ])
    return _dbos


def shutdown() -> None:
    global _dbos
    if _dbos is not None:
        DBOS.destroy()
        _dbos = None


@lru_cache
def client() -> DBOSClient:
    """Used by the API (and any process) to enqueue workflows and send signals."""
    return DBOSClient(system_database_url=system_db_url())
