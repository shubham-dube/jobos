"""Application lifecycle helpers used by workflows and the API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobos.db.models import Application, ApplicationEvent, Company, Document, Job, Match
from jobos.domain.states import APPLIED, AppState, check_transition
from jobos.forms.recipes import site_key_for


class DuplicateApplication(ValueError):
    pass


def create_application(s: Session, candidate_id: uuid.UUID, job_id: uuid.UUID, *, cooldown_days: int = 60,
                       actor: str = "user") -> Application:
    existing = s.scalar(select(Application).where(Application.candidate_id == candidate_id,
                                                  Application.job_id == job_id))
    if existing:
        if existing.state in (AppState.failed, AppState.expired, AppState.cancelled, AppState.skipped):
            transition(s, existing, AppState.queued, actor=actor, data={"reason": "re-queued"})
            return existing
        raise DuplicateApplication(f"already {existing.state}")
    job = s.get(Job, job_id)
    if job is None:
        raise ValueError("job not found")
    # same company + same normalized title recently applied → duplicate (FR-POL-2)
    since = datetime.now(UTC) - timedelta(days=cooldown_days)
    dup = s.scalar(
        select(Application.id).join(Job, Job.id == Application.job_id)
        .where(Application.candidate_id == candidate_id, Job.company_name == job.company_name,
               Job.title_norm == job.title_norm, Application.created_at >= since,
               Application.state.in_([st.value for st in APPLIED]))
        .limit(1))
    if dup:
        raise DuplicateApplication("applied to the same role at this company recently")
    match = s.scalar(select(Match).where(Match.candidate_id == candidate_id, Match.job_id == job_id))
    app = Application(candidate_id=candidate_id, job_id=job_id, match_id=match.id if match else None,
                      state=AppState.queued.value)
    s.add(app)
    s.flush()
    s.add(ApplicationEvent(application_id=app.id, from_state="", to_state=AppState.queued.value, actor=actor))
    if match:
        match.status = "shortlisted"
    return app


def transition(s: Session, app: Application, new_state: AppState | str, *, actor: str = "system",
               data: dict[str, Any] | None = None) -> None:
    new = AppState(new_state)
    check_transition(app.state, new)
    if app.state == new.value:
        return
    s.add(ApplicationEvent(application_id=app.id, from_state=app.state, to_state=new.value, actor=actor,
                           data=data or {}))
    app.state = new.value
    app.updated_at = datetime.now(UTC)
    if new == AppState.submitted and app.submitted_at is None:
        app.submitted_at = datetime.now(UTC)


def pick_resume(s: Session, candidate_id: uuid.UUID, label: str = "") -> Document | None:
    docs = s.scalars(select(Document).where(Document.candidate_id == candidate_id, Document.kind == "resume",
                                            Document.job_id.is_(None))  # job-specific variants never reused
                     .order_by(Document.created_at)).all()
    if label:
        for d in docs:
            if d.label.lower() == label.lower():
                return d
    for d in docs:
        if d.is_default:
            return d
    return docs[0] if docs else None


def attempt_context(s: Session, app_id: uuid.UUID) -> dict[str, Any]:
    app = s.get(Application, app_id)
    assert app is not None
    job = s.get(Job, app.job_id)
    assert job is not None
    match = s.get(Match, app.match_id) if app.match_id else None
    company = s.get(Company, job.company_id) if job.company_id else None
    doc = s.get(Document, app.document_id) if app.document_id else pick_resume(
        s, app.candidate_id, match.resume_label if match else "")
    if doc and app.document_id is None:
        app.document_id = doc.id
    board = company.board_token if company else ""
    return {
        "application_id": str(app.id), "candidate_id": str(app.candidate_id), "job_id": str(job.id),
        "attempt": app.attempt, "apply_url": job.apply_url, "ats": job.ats, "company": job.company_name,
        "title": job.title, "countries": job.countries, "remote": job.remote_type == "remote",
        "site_key": site_key_for(job.ats, job.apply_url, board), "board_token": board,
        "match_score": match.score if match else None, "legitimacy": match.legitimacy if match else None,
        "dry_run": bool(app.dry_run), "resume_document_id": str(doc.id) if doc else "", "resume_filename": doc.filename if doc else "",
        "documents": default_documents(s, app.candidate_id, job.id),
    }


def default_documents(s: Session, candidate_id: uuid.UUID, job_id: uuid.UUID | None = None) -> dict[str, str]:
    """Non-resume documents by kind, e.g. {"transcript": "<id>"}: this job's own documents first (a generated
    cover letter), then the default, then the newest. Other jobs' documents are never used."""
    out: dict[str, str] = {}
    scope = Document.job_id.is_(None) if job_id is None else (Document.job_id.is_(None) | (Document.job_id == job_id))
    rows = s.scalars(select(Document).where(Document.candidate_id == candidate_id, Document.kind != "resume", scope)
                     .order_by(Document.job_id.is_(None), Document.is_default.desc(), Document.created_at.desc()))
    for d in rows:
        out.setdefault(d.kind, str(d.id))
    return out


def submitted_counts(s: Session, candidate_id: uuid.UUID, company: str) -> tuple[int, int]:
    since = datetime.now(UTC) - timedelta(days=1)
    base = select(func.count()).select_from(Application).join(Job, Job.id == Application.job_id).where(
        Application.candidate_id == candidate_id, Application.submitted_at >= since)
    total = s.scalar(base) or 0
    per_company = s.scalar(base.where(Job.company_name == company)) or 0
    return total, per_company
