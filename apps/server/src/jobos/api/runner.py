"""Runner protocol endpoints (jobos_common.runner)."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from jobos.config import get_settings
from jobos.db import session_scope
from jobos.db.models import Document, Runner
from jobos.services import runner_gateway as rg
from jobos.services.storage import put_b64
from jobos_common import PROTOCOL_VERSION
from jobos_common.runner import RunnerHello, TaskResult

from .deps import db, runner_auth

router = APIRouter(prefix="/runner/v1", tags=["runner"])


@router.post("/hello")
def hello(body: RunnerHello, runner: Runner = Depends(runner_auth), s: Session = Depends(db)) -> dict:
    if body.protocol_version != PROTOCOL_VERSION:
        raise HTTPException(426, f"protocol {body.protocol_version} unsupported; server speaks {PROTOCOL_VERSION}")
    r = s.get(Runner, runner.id)
    assert r is not None
    r.version, r.os, r.max_sessions, r.last_seen_at = body.runner_version, body.os[:80], body.max_sessions, datetime.now(UTC)
    return {"runner_id": str(r.id), "name": r.name}


@router.post("/tasks/next", response_model=None)
def next_task(wait: int = 25, runner: Runner = Depends(runner_auth)) -> Response | dict:
    deadline = time.monotonic() + max(0, min(wait, 50))
    while True:
        with session_scope() as s:
            r = s.get(Runner, runner.id)
            assert r is not None
            r.last_seen_at = datetime.now(UTC)
            task = rg.lease_next(s, r)
        if task is not None:
            return task.model_dump(mode="json")
        if time.monotonic() >= deadline:
            return Response(status_code=204)
        time.sleep(1.0)


@router.post("/tasks/{task_id}/result")
def task_result(task_id: uuid.UUID, body: TaskResult, runner: Runner = Depends(runner_auth)) -> dict:
    artifacts = []
    for i, a in enumerate(body.artifacts):
        rel = f"evidence/tasks/{task_id}/{i}-{a.name}.jpg"
        artifacts.append({"name": a.name, "path": put_b64(rel, a.data_b64)})
    message = {"ok": body.ok, "data": body.data, "error": body.error,
               "error_kind": body.error_kind.value if body.error_kind else None, "artifacts": artifacts}
    with session_scope() as s:
        row = rg.complete_task(s, task_id, runner, message)
        if row is None:
            return {"accepted": False}
        workflow_id, topic = row.workflow_id, row.topic
    from jobos.workflows.runtime import client

    if workflow_id:
        client().send(workflow_id, message, topic)
    return {"accepted": True}


@router.get("/files/{doc_id}")
def file(doc_id: uuid.UUID, runner: Runner = Depends(runner_auth), s: Session = Depends(db)) -> FileResponse:
    d = s.get(Document, doc_id)
    if d is None or d.candidate_id != runner.candidate_id:
        raise HTTPException(404)
    path = (get_settings().data_dir / d.storage_path).resolve()
    return FileResponse(path, media_type=d.content_type, filename=d.filename)
