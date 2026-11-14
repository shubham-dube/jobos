"""Inbox sync workflow (scheduled)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from dbos import DBOS
from sqlalchemy import select

from jobos.db import session_scope
from jobos.db.models import Mailbox
from jobos.llm import get_gateway
from jobos.services.inbox import sync_mailbox


@DBOS.step()
def mailboxes_step() -> list[str]:
    with session_scope() as s:
        return [str(m.id) for m in s.scalars(select(Mailbox).where(Mailbox.enabled.is_(True)))]


@DBOS.step(retries_allowed=True, max_attempts=2, interval_seconds=30)
def sync_step(mailbox_id: str) -> dict[str, Any]:
    with session_scope() as s:
        mb = s.get(Mailbox, uuid.UUID(mailbox_id))
        if mb is None:
            return {}
        try:
            return sync_mailbox(s, get_gateway(), mb)
        except Exception as exc:
            mb.last_error = str(exc)[:500]
            return {"error": str(exc)}


@DBOS.workflow()
def inbox_tick(scheduled_time: datetime, context: Any) -> None:
    for mb in mailboxes_step():
        sync_step(mb)
