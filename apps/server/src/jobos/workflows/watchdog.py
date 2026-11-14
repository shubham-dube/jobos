"""Watchdog: resume application workflows whose durable sleep should have ended but made no progress.

DBOS replays recorded steps on resume (each step runs at most once), so resuming is safe.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog
from dbos import DBOS
from sqlalchemy import text

from jobos.db import session_scope

log = structlog.get_logger(__name__)

_STALLED_SQL = text("""
    SELECT w.workflow_uuid, o.output, o.started_at_epoch_ms
    FROM dbos.workflow_status w
    JOIN LATERAL (
        SELECT function_name, output, started_at_epoch_ms FROM dbos.operation_outputs
        WHERE workflow_uuid = w.workflow_uuid ORDER BY function_id DESC LIMIT 1
    ) o ON true
    WHERE w.status = 'PENDING' AND w.name = 'application_workflow' AND o.function_name = 'DBOS.sleep'
""")


@DBOS.step()
def stalled_workflows_step(grace_s: float = 120.0) -> list[str]:
    now = time.time()
    out: list[str] = []
    with session_scope() as s:
        for wf_id, output, _started in s.execute(_STALLED_SQL):
            try:
                wake_at = float(output)
            except (TypeError, ValueError):
                continue
            if wake_at + grace_s < now:
                out.append(wf_id)
    return out


@DBOS.workflow()
def watchdog_tick(scheduled_time: datetime, context: Any) -> None:
    for wf_id in stalled_workflows_step():
        log.warning("watchdog.resume", workflow=wf_id)
        DBOS.resume_workflow(wf_id)
