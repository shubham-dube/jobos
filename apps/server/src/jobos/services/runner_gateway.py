"""Runner task queue (browser-execution.md §4). Workflows create tasks; runners lease and complete them."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from jobos.db.models import Runner, RunnerTaskRecord
from jobos_common.runner import RunnerTask, TaskType

# Tasks that must never be re-executed automatically after a lost lease (could double-submit).
NON_IDEMPOTENT = {TaskType.submit.value}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_runner(s: Session, candidate_id: uuid.UUID, name: str) -> tuple[Runner, str]:
    token = "jr_" + secrets.token_urlsafe(32)
    r = Runner(candidate_id=candidate_id, name=name, token_hash=hash_token(token))
    s.add(r)
    s.flush()
    return r, token


def runner_by_token(s: Session, token: str) -> Runner | None:
    return s.scalar(select(Runner).where(Runner.token_hash == hash_token(token), Runner.revoked.is_(False)))


def create_task(s: Session, *, candidate_id: uuid.UUID, workflow_id: str, idempotency_key: str, type: TaskType,
                session_id: str, payload: dict[str, Any], timeout_s: int = 180) -> RunnerTaskRecord:
    existing = s.scalar(select(RunnerTaskRecord).where(RunnerTaskRecord.idempotency_key == idempotency_key))
    if existing:
        return existing
    t = RunnerTaskRecord(idempotency_key=idempotency_key, candidate_id=candidate_id, workflow_id=workflow_id,
                         topic="", type=type.value, session_id=session_id, payload=payload, timeout_s=timeout_s)
    s.add(t)
    s.flush()
    t.topic = f"task:{t.id}"
    return t


def lease_next(s: Session, runner: Runner) -> RunnerTask | None:
    expire_stale(s)
    row = s.scalar(
        select(RunnerTaskRecord)
        .where(RunnerTaskRecord.candidate_id == runner.candidate_id, RunnerTaskRecord.status == "pending")
        .order_by(RunnerTaskRecord.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        return None
    row.status = "leased"
    row.runner_id = runner.id
    row.leased_at = datetime.now(UTC)
    return RunnerTask(id=str(row.id), type=TaskType(row.type), session_id=row.session_id, payload=row.payload,
                      timeout_s=row.timeout_s)


def complete_task(s: Session, task_id: uuid.UUID, runner: Runner, result: dict[str, Any]) -> RunnerTaskRecord | None:
    row = s.get(RunnerTaskRecord, task_id, with_for_update=True)
    if row is None or row.candidate_id != runner.candidate_id or row.status == "done":
        return None
    row.status = "done"
    row.result = result
    row.completed_at = datetime.now(UTC)
    return row


def expire_stale(s: Session) -> int:
    """Leases older than timeout + grace: idempotent tasks go back to pending, submits expire."""
    now = datetime.now(UTC)
    rows = s.scalars(select(RunnerTaskRecord).where(RunnerTaskRecord.status == "leased")).all()
    n = 0
    for r in rows:
        if r.leased_at and r.leased_at + timedelta(seconds=r.timeout_s + 60) < now:
            if r.type in NON_IDEMPOTENT:
                r.status = "expired"
                r.result = {"ok": False, "error": "runner lease expired during submit", "error_kind": "fatal"}
            else:
                r.status, r.runner_id, r.leased_at = "pending", None, None
            n += 1
    return n


def task_result(s: Session, task_id: uuid.UUID) -> dict[str, Any] | None:
    row = s.get(RunnerTaskRecord, task_id)
    if row and row.status in ("done", "expired"):
        return row.result
    return None


def cancel_pending_for_workflow(s: Session, workflow_id: str) -> None:
    s.execute(update(RunnerTaskRecord).where(RunnerTaskRecord.workflow_id == workflow_id,
                                             RunnerTaskRecord.status == "pending").values(status="expired"))
