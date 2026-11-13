"""Inbound webhooks: WhatsApp Cloud API replies → intervention answers (ADR-0012)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import select

from jobos.config import get_settings
from jobos.db import session_scope
from jobos.db.models import Intervention, Notification
from jobos.services import interventions as iv_svc

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
def whatsapp_verify(mode: str = Query(alias="hub.mode", default=""), token: str = Query(alias="hub.verify_token", default=""),
                    challenge: str = Query(alias="hub.challenge", default="")) -> Response:
    if mode == "subscribe" and hmac.compare_digest(token, get_settings().whatsapp_verify_token):
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(403)


@router.post("/whatsapp")
async def whatsapp_inbound(request: Request) -> dict[str, bool]:
    raw = await request.body()
    secret = get_settings().whatsapp_app_secret
    if secret:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(401, "bad signature")
    payload: dict[str, Any] = await request.json()
    allowed_sender = get_settings().whatsapp_to
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in (change.get("value") or {}).get("messages", []):
                if allowed_sender and msg.get("from") != allowed_sender:
                    log.warning("whatsapp.unknown_sender")
                    continue
                handle_message(msg)
    return {"ok": True}


def handle_message(msg: dict[str, Any]) -> None:
    reply_id, text = "", ""
    if msg.get("type") == "interactive":
        inter = msg.get("interactive", {})
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        reply_id, text = reply.get("id", ""), reply.get("title", "")
    elif msg.get("type") == "button":
        text = (msg.get("button") or {}).get("text", "")
    elif msg.get("type") == "text":
        text = (msg.get("text") or {}).get("body", "").strip()
    signal: tuple[str, dict[str, Any], str] | None = None
    with session_scope() as s:
        iv = None
        if reply_id.startswith("iv:"):
            iv = iv_svc.answer_from_reply(s, reply_id, text)
        elif text:
            context_id = (msg.get("context") or {}).get("id", "")
            target = None
            if context_id:
                n = s.scalar(select(Notification).where(Notification.external_id == context_id))
                target = s.get(Intervention, n.intervention_id) if n and n.intervention_id else None
            if target is None:  # fall back to the newest open single-question intervention
                target = s.scalar(select(Intervention).where(Intervention.status == "open",
                                                             Intervention.kind == "missing_answer")
                                  .order_by(Intervention.created_at.desc()).limit(1))
            if target is not None and target.kind == "missing_answer" and len(target.payload.get("questions", [])) == 1:
                q = target.payload["questions"][0]
                iv = iv_svc.answer_intervention(s, target.id, {"answers": {q["key"]: text},
                                                               "remember": {q["key"]: "global"}}, via="whatsapp")
        if iv is not None:
            signal = (iv.workflow_id, iv.answer or {}, iv.topic)
    if signal:
        from .dashboard import signal_workflow

        signal_workflow(*signal)
