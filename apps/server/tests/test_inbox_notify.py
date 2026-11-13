"""Inbox Clerk against a simulated IMAP server; WhatsApp payloads + webhook mapping (no network)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage

import httpx
import pytest
import respx

from jobos.config import Settings
from jobos.db.models import Application, Company, Job, Mailbox
from jobos.domain.states import AppState
from jobos.llm.fake import FakeProvider
from jobos.llm.gateway import LLMGateway
from jobos.notify.base import NotifyMessage, _wa_payload, send_whatsapp
from jobos.services.candidates import get_or_create_default_candidate
from jobos.services.inbox import sync_mailbox
from jobos.services.secrets import encrypt


def _mail(uid: int, frm: str, subject: str, body: str) -> tuple[int, bytes]:
    m = MimeMessage()
    m["From"], m["To"], m["Subject"] = frm, "me@example.com", subject
    m["Message-ID"] = f"<msg-{uid}@test>"
    m["Date"] = "Fri, 13 Nov 2026 10:00:00 +0000"
    m.set_content(body)
    return uid, bytes(m)


class FakeIMAP:
    mails: list[tuple[int, bytes]] = []
    logged_in: tuple[str, str] | None = None

    def __init__(self, host: str, port: int, timeout: int = 0):
        self.host = host

    def login(self, user: str, password: str):
        FakeIMAP.logged_in = (user, password)
        return "OK", [b""]

    def select(self, folder: str, readonly: bool = True):
        return "OK", [str(len(self.mails)).encode()]

    def uid(self, cmd: str, *args):
        if cmd == "search":
            crit = args[-1]
            lo = int(crit.split()[1].split(":")[0]) if crit.startswith("UID") else 0
            return "OK", [" ".join(str(u) for u, _ in self.mails if u >= lo).encode()]
        if cmd == "fetch":
            uid = int(args[0])
            raw = next(b for u, b in self.mails if u == uid)
            return "OK", [(f"{uid} (BODY[] {{{len(raw)}}}".encode(), raw), b")"]
        raise AssertionError(cmd)

    def logout(self):
        return "BYE", [b""]


@pytest.fixture
def submitted_app(session):
    cand = get_or_create_default_candidate(session)
    comp = Company(name="Stripe", normalized_name="stripe", ats="greenhouse", board_token=f"stripe-{uuid.uuid4().hex[:6]}")
    session.add(comp)
    session.flush()
    job = Job(company_id=comp.id, company_name="Stripe", source="greenhouse", source_job_id=uuid.uuid4().hex,
              url="https://x", apply_url="https://x", title="Backend Engineer", title_norm="backend engineer",
              fingerprint=uuid.uuid4().hex)
    session.add(job)
    session.flush()
    app = Application(candidate_id=cand.id, job_id=job.id, state=AppState.submitted.value,
                      submitted_at=datetime.now(UTC))
    session.add(app)
    session.flush()
    return cand, app


def test_inbox_sync_classifies_links_and_updates_state(session, submitted_app, monkeypatch) -> None:
    cand, app = submitted_app
    FakeIMAP.mails = [
        _mail(1, "no-reply@greenhouse.io", "Thank you for applying to Stripe", "We received your application for Backend Engineer."),
        _mail(2, "newsletter@shop.com", "50% off shoes", "Big sale this weekend"),  # no job keywords: no LLM call
        _mail(3, "recruiting@stripe.com", "Interview invitation: Backend Engineer at Stripe", "Please pick an interview slot."),
    ]
    monkeypatch.setattr("jobos.services.inbox.imaplib.IMAP4_SSL", FakeIMAP)
    fake = FakeProvider()

    def classify(req):
        text = req.messages[-1].content
        if "Interview invitation" in text:
            return {"category": "interview_request", "company": "Stripe", "job_title": "Backend Engineer", "summary": "Interview"}
        return {"category": "application_received", "company": "Stripe", "job_title": "Backend Engineer", "summary": "Received"}

    fake.on("email.classify", classify)
    mb = Mailbox(candidate_id=cand.id, label="Gmail", host="imap.gmail.com", username="me@example.com",
                 secret_enc=encrypt("app-password"))
    session.add(mb)
    session.flush()
    stats = sync_mailbox(session, LLMGateway({"fake": fake}, default_route="fake:x"), mb)
    assert stats == {"fetched": 3, "classified": 2, "linked": 2}
    assert FakeIMAP.logged_in == ("me@example.com", "app-password")
    assert app.state == AppState.interviewing.value
    assert mb.last_uid == 3
    # second sync: nothing new, no duplicates
    assert sync_mailbox(session, LLMGateway({"fake": fake}, default_route="fake:x"), mb)["fetched"] == 0


def _settings() -> Settings:
    return Settings(whatsapp_token="t", whatsapp_phone_number_id="123", whatsapp_to="917000000000",
                    whatsapp_template="jobos_action_needed")


def test_whatsapp_payload_shapes() -> None:
    s = _settings()
    buttons = _wa_payload(s, NotifyMessage("Review", "body", choices=[("iv:1:approve", "Approve & submit"), ("iv:1:reject", "Skip")]))
    assert buttons["interactive"]["type"] == "button" and len(buttons["interactive"]["action"]["buttons"]) == 2
    assert all(len(b["reply"]["title"]) <= 20 for b in buttons["interactive"]["action"]["buttons"])
    lst = _wa_payload(s, NotifyMessage("Q", "b", choices=[(f"iv:1:{i}", f"Option {i}") for i in range(6)]))
    assert lst["interactive"]["type"] == "list"
    text = _wa_payload(s, NotifyMessage("Q", "b"))
    assert text["type"] == "text"


@respx.mock
def test_whatsapp_falls_back_to_template_outside_24h_window() -> None:
    route = respx.post("https://graph.facebook.com/v21.0/123/messages").mock(side_effect=[
        httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement message"}}),
        httpx.Response(200, json={"messages": [{"id": "wamid.T"}]}),
    ])
    r = send_whatsapp(_settings(), NotifyMessage("Needs you", "body"))
    assert r.ok and r.external_id == "wamid.T"
    assert json.loads(route.calls[1].request.content)["type"] == "template"


def test_whatsapp_webhook_signature_and_reply(session, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from jobos.api import webhooks
    from jobos.config import get_settings
    from jobos.services.interventions import create_intervention

    cand = get_or_create_default_candidate(session)
    iv = create_intervention(session, candidate_id=cand.id, workflow_id="wf-1", kind="review_before_submit",
                             title="Review", payload={})
    session.commit()
    sent: list[tuple] = []
    monkeypatch.setattr("jobos.api.dashboard.signal_workflow", lambda *a: sent.append(a))
    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "shh")
    monkeypatch.setattr(settings, "whatsapp_to", "917000000000")

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(webhooks.router)
    client = TestClient(app)
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [{
        "from": "917000000000", "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": f"iv:{iv.id}:approve", "title": "Approve"}}}]}}]}]})
    bad = client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=wrong"})
    assert bad.status_code == 401
    sig = "sha256=" + hmac.new(b"shh", body.encode(), hashlib.sha256).hexdigest()
    ok = client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sig,
                                                                  "Content-Type": "application/json"})
    assert ok.status_code == 200
    assert sent and sent[0][0] == "wf-1" and sent[0][1] == {"decision": "approve"}
    # verification handshake
    v = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": settings.whatsapp_verify_token,
                                                 "hub.challenge": "42"})
    assert v.text == "42"


def test_job_alert_email_becomes_jobs(session, monkeypatch) -> None:
    from sqlalchemy import select

    from jobos.services.job_alerts import ingest_job_alert

    fake = FakeProvider()
    fake.on("email.job_alert", lambda req: {"jobs": [
        {"title": "Backend Engineer", "company": "Acme Pay", "location": "Bengaluru, India",
         "url": "https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc&refId=x"},
        {"title": "Platform Engineer", "company": "Newco", "location": "Remote",
         "url": "https://jobs.lever.co/newco-test/1234-abcd"},
    ]})
    n = ingest_job_alert(session, LLMGateway({"fake": fake}, default_route="fake:x"), "Jobs for you", "...",
                         "jobalerts-noreply@linkedin.com")
    assert n == 1
    job = session.scalar(select(Job).where(Job.source == "email_alert", Job.company_name == "Acme Pay"))
    assert job.apply_url == "https://www.linkedin.com/jobs/view/4012345678" and job.ats == "linkedin"
    assert job.countries == ["IN"]
    assert session.scalar(select(Company).where(Company.ats == "lever", Company.board_token == "newco-test"))
    # idempotent
    assert ingest_job_alert(session, LLMGateway({"fake": fake}, default_route="fake:x"), "Jobs", "...", "x") == 0
