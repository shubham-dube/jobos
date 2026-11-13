"""Interventions: create, notify, answer (FR-HITL-*)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from jobos.config import get_settings
from jobos.db.models import Intervention, Notification
from jobos.notify import NotifyMessage, send_all
from jobos.services.candidates import get_candidate_settings


def create_intervention(s: Session, *, candidate_id: uuid.UUID, workflow_id: str, kind: str, title: str,
                        payload: dict[str, Any], application_id: uuid.UUID | None = None,
                        idempotency_key: str = "") -> Intervention:
    from sqlalchemy import select

    topic = f"intervention:{idempotency_key or uuid.uuid4()}"
    existing = s.scalar(select(Intervention).where(Intervention.topic == topic))
    if existing:
        return existing
    hours = get_settings().intervention_timeout_h
    iv = Intervention(candidate_id=candidate_id, workflow_id=workflow_id, topic=topic, kind=kind, title=title,
                      payload=payload, application_id=application_id,
                      expires_at=datetime.now(UTC) + timedelta(hours=hours))
    s.add(iv)
    s.flush()
    return iv


def notify_intervention(s: Session, iv: Intervention) -> None:
    settings = get_settings()
    cs = get_candidate_settings(s, iv.candidate_id)
    link = f"{settings.web_base_url}/inbox/{iv.id}"
    body, choices = _summary(iv)
    results = send_all(NotifyMessage(title=iv.title, body=body, link=link, choices=choices), cs.notify_channels)
    for r in results:
        if r.channel != "console":
            s.add(Notification(candidate_id=iv.candidate_id, intervention_id=iv.id, channel=r.channel,
                               external_id=r.external_id, status="sent" if r.ok else "failed", error=r.error[:500]))


def _summary(iv: Intervention) -> tuple[str, list[tuple[str, str]]]:
    p = iv.payload or {}
    job = p.get("job", {})
    head = f"{job.get('title', '')} — {job.get('company', '')}".strip(" —")
    if iv.kind == "missing_answer":
        qs = p.get("questions", [])
        lines = [head, f"{len(qs)} question(s) need your answer:"] + [f"• {q['label'][:120]}" for q in qs[:5]]
        choices: list[tuple[str, str]] = []
        if len(qs) == 1 and qs[0].get("options") and len(qs[0]["options"]) <= 10:
            choices = [(f"iv:{iv.id}:{i}", o) for i, o in enumerate(qs[0]["options"])]
        elif len(qs) == 1:
            lines.append("Reply to this message with your answer.")
        return "\n".join(lines), choices
    if iv.kind == "review_before_submit":
        n = sum(len(pg.get("fields", [])) for pg in p.get("pages", []))
        gen = p.get("gate", {}).get("facts", {}).get("generated_fields", 0)
        return (f"{head}\nReady to submit: {n} fields filled, {gen} written by AI. Match {p.get('match_score', '?')}.",
                [(f"iv:{iv.id}:approve", "Approve & submit"), (f"iv:{iv.id}:reject", "Skip job")])
    if iv.kind == "account_creation_consent":
        return (f"{head}\n{p.get('message', '')}",
                [(f"iv:{iv.id}:approve", "Create account"), (f"iv:{iv.id}:always", "Always allow"),
                 (f"iv:{iv.id}:reject", "No")])
    if iv.kind in ("login_required", "captcha", "blocked", "verify_email"):
        return (f"{head}\n{p.get('message', 'Please complete this step in the JobOS browser window on your computer.')}",
                [(f"iv:{iv.id}:done", "Done")])
    return head or iv.title, []


def answer_intervention(s: Session, iv_id: uuid.UUID, answer: dict[str, Any], via: str = "web") -> Intervention | None:
    iv = s.get(Intervention, iv_id, with_for_update=True)
    if iv is None or iv.status != "open":
        return None
    iv.status = "answered"
    iv.answer = answer
    iv.answered_via = via
    iv.answered_at = datetime.now(UTC)
    return iv


def answer_from_reply(s: Session, reply_id: str, text: str = "") -> Intervention | None:
    """Map a WhatsApp button/list reply id ("iv:<uuid>:<choice>") to an intervention answer."""
    try:
        _, iv_s, choice = reply_id.split(":", 2)
        iv_id = uuid.UUID(iv_s)
    except ValueError:
        return None
    iv = s.get(Intervention, iv_id)
    if iv is None:
        return None
    if iv.kind == "review_before_submit":
        return answer_intervention(s, iv_id, {"decision": "approve" if choice == "approve" else "reject"}, "whatsapp")
    if iv.kind == "account_creation_consent":
        return answer_intervention(s, iv_id, {"decision": choice if choice in ("approve", "always") else "reject"},
                                   "whatsapp")
    if iv.kind == "missing_answer":
        q = (iv.payload.get("questions") or [{}])[0]
        opts = q.get("options") or []
        value = opts[int(choice)] if choice.isdigit() and int(choice) < len(opts) else text
        return answer_intervention(s, iv_id, {"answers": {q.get("key"): value}, "remember": {q.get("key"): "global"}},
                                   "whatsapp")
    return answer_intervention(s, iv_id, {"done": True}, "whatsapp")
