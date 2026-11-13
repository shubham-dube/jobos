"""Durable building blocks: call the runner and wait; ask the human and wait.

Workflow code must stay deterministic: all I/O happens in @DBOS.step functions.
"""

from __future__ import annotations

import uuid
from typing import Any

from dbos import DBOS

from jobos.config import get_settings
from jobos.db import session_scope
from jobos.services import interventions as iv_svc
from jobos.services import runner_gateway as rg
from jobos_common.runner import TaskType


class Counter:
    """Deterministic per-workflow sequence for idempotency keys."""

    def __init__(self) -> None:
        self.n = 0

    def next(self, label: str) -> str:
        self.n += 1
        return f"{DBOS.workflow_id}:{self.n}:{label}"


@DBOS.step()
def create_runner_task_step(candidate_id: str, key: str, task_type: str, session_id: str,
                            payload: dict[str, Any], timeout_s: int) -> str:
    with session_scope() as s:
        t = rg.create_task(s, candidate_id=uuid.UUID(candidate_id), workflow_id=DBOS.workflow_id or "",
                           idempotency_key=key, type=TaskType(task_type), session_id=session_id,
                           payload=payload, timeout_s=timeout_s)
        return str(t.id)


@DBOS.step()
def read_task_result_step(task_id: str) -> dict[str, Any] | None:
    with session_scope() as s:
        return rg.task_result(s, uuid.UUID(task_id))


@DBOS.step()
def notify_runner_offline_step(candidate_id: str, workflow_id: str, key: str) -> None:
    with session_scope() as s:
        iv = iv_svc.create_intervention(
            s, candidate_id=uuid.UUID(candidate_id), workflow_id=workflow_id, kind="runner_offline",
            title="Your JobOS runner is offline", idempotency_key=key,
            payload={"message": "Start the JobOS runner on your computer so queued applications can continue."})
        iv.status = "answered"  # informational only, nobody waits on it
        iv_svc.notify_intervention(s, iv)


def fire_runner(ctr: Counter, candidate_id: str, label: str, task_type: TaskType, session_id: str,
                payload: dict[str, Any]) -> None:
    """Create a runner task without waiting for the result (e.g. closing a tab)."""
    create_runner_task_step(candidate_id, ctr.next(label), task_type.value, session_id, payload, 60)


def call_runner(ctr: Counter, candidate_id: str, label: str, task_type: TaskType, session_id: str,
                payload: dict[str, Any], timeout_s: int = 180, max_wait_s: int = 6 * 3600) -> dict[str, Any]:
    """Create a runner task and durably wait for its result. Returns TaskResult as dict."""
    key = ctr.next(label)
    task_id = create_runner_task_step(candidate_id, key, task_type.value, session_id, payload, timeout_s)
    waited = 0
    notified = False
    while waited < max_wait_s:
        wait = timeout_s + 120 if waited == 0 else 900
        msg = DBOS.recv(topic=f"task:{task_id}", timeout_seconds=wait)
        if msg is not None:
            return msg
        res = read_task_result_step(task_id)
        if res is not None:
            return res
        waited += wait
        if not notified:
            notify_runner_offline_step(candidate_id, DBOS.workflow_id or "", f"{key}:offline")
            notified = True
    return {"ok": False, "error": "runner did not respond", "error_kind": "retryable"}


@DBOS.step()
def create_intervention_step(candidate_id: str, application_id: str | None, key: str, kind: str, title: str,
                             payload: dict[str, Any]) -> dict[str, str]:
    with session_scope() as s:
        iv = iv_svc.create_intervention(
            s, candidate_id=uuid.UUID(candidate_id), workflow_id=DBOS.workflow_id or "", kind=kind, title=title,
            payload=payload, application_id=uuid.UUID(application_id) if application_id else None,
            idempotency_key=key)
        iv_svc.notify_intervention(s, iv)
        return {"id": str(iv.id), "topic": iv.topic}


@DBOS.step()
def expire_intervention_step(iv_id: str) -> dict[str, Any] | None:
    from jobos.db.models import Intervention

    with session_scope() as s:
        iv = s.get(Intervention, uuid.UUID(iv_id))
        if iv is None:
            return None
        if iv.status == "answered":  # answered but the signal was missed
            return iv.answer
        iv.status = "expired"
        return None


def ask_human(ctr: Counter, candidate_id: str, application_id: str | None, kind: str, title: str,
              payload: dict[str, Any]) -> dict[str, Any] | None:
    """Create an intervention, notify, and wait (durably) for the answer. None = expired."""
    key = ctr.next(f"iv-{kind}")
    iv = create_intervention_step(candidate_id, application_id, key, kind, title, payload)
    hours = get_settings().intervention_timeout_h
    msg = DBOS.recv(topic=iv["topic"], timeout_seconds=hours * 3600)
    if msg is not None:
        return None if msg.get("cancelled") else msg
    return expire_intervention_step(iv["id"])
