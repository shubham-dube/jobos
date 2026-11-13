from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from jobos import __version__
from jobos.config import get_settings
from jobos.db import session_scope
from jobos.services.candidates import get_or_create_default_candidate
from jobos.services.discovery import seed_companies

from . import dashboard, runner, webhooks

log = structlog.get_logger(__name__)


def create_app(launch_workers: bool | None = None) -> FastAPI:
    settings = get_settings()
    run_workers = settings.worker_role in ("worker", "all") if launch_workers is None else launch_workers

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with session_scope() as s:
            get_or_create_default_candidate(s)
            added = seed_companies(s)
            if added:
                log.info("seeded companies", added=added)
        if run_workers:
            from jobos.workflows import runtime

            await asyncio.to_thread(runtime.launch)  # DBOS's sync API must not run on the event loop
        yield
        if run_workers:
            from jobos.workflows import runtime

            await asyncio.to_thread(runtime.shutdown)

    app = FastAPI(title="JobOS API", version=__version__, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(dashboard.router)
    app.include_router(runner.router)
    app.include_router(webhooks.router)
    return app
