"""Notification fan-out (ADR-0012): WhatsApp Cloud API, Resend email, console."""

from __future__ import annotations

import html
from dataclasses import dataclass, field

import httpx
import structlog

from jobos.config import Settings, get_settings

log = structlog.get_logger(__name__)


@dataclass
class NotifyMessage:
    title: str
    body: str
    link: str = ""
    # quick replies: (reply_id, label). WhatsApp shows ≤3 as buttons, ≤10 as a list.
    choices: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SendResult:
    channel: str
    ok: bool
    external_id: str = ""
    error: str = ""


def send_email(settings: Settings, msg: NotifyMessage) -> SendResult:
    if not (settings.resend_api_key and settings.email_from and settings.notify_email_to):
        return SendResult("email", False, error="email not configured")
    body_html = "<br>".join(html.escape(line) for line in msg.body.splitlines())
    if msg.link:
        body_html += f'<p><a href="{html.escape(msg.link)}">Open in JobOS</a></p>'
    try:
        r = httpx.post("https://api.resend.com/emails", timeout=20,
                       headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                       json={"from": settings.email_from, "to": [settings.notify_email_to],
                             "subject": f"[JobOS] {msg.title}", "html": f"<p>{body_html}</p>"})
        if r.status_code >= 300:
            return SendResult("email", False, error=f"HTTP {r.status_code}: {r.text[:200]}")
        return SendResult("email", True, external_id=r.json().get("id", ""))
    except httpx.HTTPError as exc:
        return SendResult("email", False, error=str(exc))


def _wa_payload(settings: Settings, msg: NotifyMessage) -> dict:
    text = f"*{msg.title}*\n{msg.body}"
    if msg.link:
        text += f"\n\n{msg.link}"
    text = text[:1000]
    base = {"messaging_product": "whatsapp", "to": settings.whatsapp_to}
    if 0 < len(msg.choices) <= 3:
        return {**base, "type": "interactive", "interactive": {
            "type": "button", "body": {"text": text},
            "action": {"buttons": [{"type": "reply", "reply": {"id": cid[:256], "title": label[:20]}}
                                   for cid, label in msg.choices]}}}
    if 3 < len(msg.choices) <= 10:
        return {**base, "type": "interactive", "interactive": {
            "type": "list", "body": {"text": text},
            "action": {"button": "Choose", "sections": [{"title": "Options", "rows": [
                {"id": cid[:200], "title": label[:24], "description": label[24:96]} for cid, label in msg.choices]}]}}}
    return {**base, "type": "text", "text": {"body": text, "preview_url": False}}


def send_whatsapp(settings: Settings, msg: NotifyMessage) -> SendResult:
    if not (settings.whatsapp_token and settings.whatsapp_phone_number_id and settings.whatsapp_to):
        return SendResult("whatsapp", False, error="whatsapp not configured")
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    try:
        r = httpx.post(url, headers=headers, json=_wa_payload(settings, msg), timeout=20)
        data = r.json()
        if r.status_code >= 300:
            err = (data.get("error") or {})
            # outside the 24h customer-service window: send the approved template instead
            if err.get("code") in (131047, 131026) and settings.whatsapp_template:
                tpl = {"messaging_product": "whatsapp", "to": settings.whatsapp_to, "type": "template",
                       "template": {"name": settings.whatsapp_template, "language": {"code": "en"},
                                    "components": [{"type": "body", "parameters": [
                                        {"type": "text", "text": msg.title[:60]}]}]}}
                r = httpx.post(url, headers=headers, json=tpl, timeout=20)
                data = r.json()
                if r.status_code < 300:
                    return SendResult("whatsapp", True, external_id=data["messages"][0]["id"])
            return SendResult("whatsapp", False, error=f"HTTP {r.status_code}: {str(err)[:200]}")
        return SendResult("whatsapp", True, external_id=data["messages"][0]["id"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return SendResult("whatsapp", False, error=str(exc))


def send_all(msg: NotifyMessage, channels: list[str], settings: Settings | None = None) -> list[SendResult]:
    settings = settings or get_settings()
    results: list[SendResult] = [SendResult("console", True)]
    log.info("notify", title=msg.title, link=msg.link, choices=[c[1] for c in msg.choices])
    if settings.is_test:
        return results
    if "whatsapp" in channels:
        results.append(send_whatsapp(settings, msg))
    if "email" in channels:
        results.append(send_email(settings, msg))
    for r in results:
        if not r.ok:
            log.warning("notify.failed", channel=r.channel, error=r.error)
    return results
