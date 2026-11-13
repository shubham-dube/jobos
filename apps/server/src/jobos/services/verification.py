"""Find employer email-verification links in the candidate's connected inboxes (FR-ACC-3)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobos.db.models import EmailMessage, Mailbox
from jobos.llm import LLMGateway
from jobos.services.inbox import sync_mailbox

_VERIFY_HINT = re.compile(r"verif|confirm|activate|validate", re.I)


def find_verification_link(s: Session, gateway: LLMGateway | None, candidate_id: uuid.UUID, *, host: str,
                           company: str, since: datetime, sync: bool = True) -> str | None:
    mailboxes = s.scalars(select(Mailbox).where(Mailbox.candidate_id == candidate_id, Mailbox.enabled.is_(True))).all()
    if sync:
        for mb in mailboxes:
            try:
                sync_mailbox(s, gateway, mb, max_messages=50)
            except Exception as exc:  # a broken mailbox must not stop the application
                mb.last_error = str(exc)[:500]
    if not mailboxes:
        return None
    rows = s.scalars(select(EmailMessage).where(
        EmailMessage.mailbox_id.in_([m.id for m in mailboxes]), EmailMessage.category == "verification_code",
        EmailMessage.received_at >= since).order_by(EmailMessage.received_at.desc())).all()
    base = ".".join(host.split(".")[-3:]) if host else ""
    company_l = company.lower()
    for row in rows:
        text = f"{row.from_addr} {row.subject} {row.snippet}".lower()
        related = (base and base in text) or (company_l and company_l in text) or "workday" in text
        if not related:
            continue
        links = [link for link in (row.extracted or {}).get("links", []) if link.startswith("http")]
        links.sort(key=lambda link: (base not in link, not _VERIFY_HINT.search(link)))
        if links:
            return links[0]
    return None
