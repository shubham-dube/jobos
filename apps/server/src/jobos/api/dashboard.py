"""Dashboard API (/api/v1). All endpoints are scoped to the authenticated candidate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobos.config import get_settings
from jobos.db.models import (
    Answer,
    Application,
    ApplicationEvent,
    Company,
    Document,
    EmailMessage,
    FormPageRecord,
    Intervention,
    Job,
    LLMCall,
    Mailbox,
    Match,
    Runner,
    SearchProfile,
)
from jobos.domain.settings import CandidateSettings, SearchFilters
from jobos.domain.states import ACTIVE, AppState
from jobos.forms.answer_bank import save_answer
from jobos.llm import get_gateway
from jobos.services import interventions as iv_svc
from jobos.services import runner_gateway as rg
from jobos.services.applications import DuplicateApplication, create_application, transition
from jobos.services.candidates import (
    get_candidate_settings,
    get_profile,
    save_candidate_settings,
    save_profile,
)
from jobos.services.discovery import add_company, crawl_company
from jobos.services.inbox import PRESETS
from jobos.services.profile_import import build_profile, extract_text
from jobos.services.secrets import encrypt
from jobos.services.storage import put_bytes, sha256
from jobos.sources.ats import detect_ats_from_url
from jobos_common.profile import MasterProfile

from .deps import AuthContext, db, owner

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def _uuid(v: str) -> uuid.UUID:
    try:
        return uuid.UUID(v)
    except ValueError as exc:
        raise HTTPException(404) from exc


# ----------------------------------------------------------------------------- me / settings --

@router.get("/me")
def me(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    profile = get_profile(s, auth.candidate_id)
    return {"candidate_id": str(auth.candidate_id), "name": profile.basics.full_name,
            "has_profile": bool(profile.basics.email), "settings": get_candidate_settings(s, auth.candidate_id)}


@router.get("/settings")
def get_settings_(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> CandidateSettings:
    return get_candidate_settings(s, auth.candidate_id)


@router.put("/settings")
def put_settings(body: CandidateSettings, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> CandidateSettings:
    save_candidate_settings(s, auth.candidate_id, body)
    return body


# ------------------------------------------------------------------------------------ profile --

@router.get("/profile")
def get_profile_(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> MasterProfile:
    return get_profile(s, auth.candidate_id)


@router.put("/profile")
def put_profile(body: MasterProfile, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, int]:
    return {"version": save_profile(s, auth.candidate_id, body, source="manual")}


@router.post("/profile/import")
def import_profile(file: UploadFile | None = File(default=None), text: str = Form(default=""),
                   auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    """Profile Builder agent: PDF/DOCX-text/Markdown or pasted text → MasterProfile (new version)."""
    if file is not None:
        content = extract_text(file.filename or "upload.txt", file.file.read())
    else:
        content = text
    if len(content.strip()) < 100:
        raise HTTPException(400, "not enough text to build a profile")
    profile = build_profile(get_gateway(), content, ref=f"profile:{auth.candidate_id}")
    version = save_profile(s, auth.candidate_id, profile, source="import")
    return {"version": version, "profile": profile}


# ---------------------------------------------------------------------------------- documents --

@router.get("/documents")
def list_documents(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    docs = s.scalars(select(Document).where(Document.candidate_id == auth.candidate_id).order_by(Document.created_at))
    return [{"id": str(d.id), "kind": d.kind, "label": d.label, "filename": d.filename, "is_default": d.is_default,
             "created_at": d.created_at} for d in docs]


@router.post("/documents")
def upload_document(file: UploadFile = File(...), label: str = Form(default=""), kind: str = Form(default="resume"),
                    is_default: bool = Form(default=False), auth: AuthContext = Depends(owner),
                    s: Session = Depends(db)) -> dict[str, Any]:
    data = file.file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "max 10MB")
    filename = (file.filename or "document.pdf").replace("/", "_").replace("\\", "_")
    doc_id = uuid.uuid4()
    path = put_bytes(f"documents/{auth.candidate_id}/{doc_id}/{filename}", data)
    if is_default:
        for d in s.scalars(select(Document).where(Document.candidate_id == auth.candidate_id, Document.kind == kind)):
            d.is_default = False
    d = Document(id=doc_id, candidate_id=auth.candidate_id, kind=kind, label=label, filename=filename,
                 content_type=file.content_type or "application/pdf", storage_path=path, sha256=sha256(data),
                 text=extract_text(filename, data)[:50000] if filename.lower().endswith((".pdf", ".txt", ".md")) else "",
                 is_default=is_default)
    s.add(d)
    return {"id": str(d.id)}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    d = s.get(Document, _uuid(doc_id))
    if d is None or d.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    s.delete(d)
    return {"deleted": True}


# ---------------------------------------------------------------------------- search profiles --

class SearchProfileIn(BaseModel):
    name: str
    enabled: bool = True
    auto_apply: bool = False
    schedule_minutes: int = 360
    filters: SearchFilters = SearchFilters()


@router.get("/search-profiles")
def list_search_profiles(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    rows = s.scalars(select(SearchProfile).where(SearchProfile.candidate_id == auth.candidate_id))
    return [{"id": str(r.id), "name": r.name, "enabled": r.enabled, "auto_apply": r.auto_apply,
             "schedule_minutes": r.schedule_minutes, "filters": r.filters, "last_run_at": r.last_run_at} for r in rows]


@router.post("/search-profiles")
def create_search_profile(body: SearchProfileIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, str]:
    sp = SearchProfile(candidate_id=auth.candidate_id, name=body.name, enabled=body.enabled, auto_apply=body.auto_apply,
                       schedule_minutes=body.schedule_minutes, filters=body.filters.model_dump())
    s.add(sp)
    s.flush()
    return {"id": str(sp.id)}


@router.put("/search-profiles/{sp_id}")
def update_search_profile(sp_id: str, body: SearchProfileIn, auth: AuthContext = Depends(owner),
                          s: Session = Depends(db)) -> dict[str, bool]:
    sp = s.get(SearchProfile, _uuid(sp_id))
    if sp is None or sp.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    sp.name, sp.enabled, sp.auto_apply = body.name, body.enabled, body.auto_apply
    sp.schedule_minutes, sp.filters = body.schedule_minutes, body.filters.model_dump()
    return {"ok": True}


@router.post("/search-profiles/{sp_id}/run")
def run_search_profile(sp_id: str, max_llm_scores: int = 50, auth: AuthContext = Depends(owner),
                       s: Session = Depends(db)) -> dict[str, str]:
    sp = s.get(SearchProfile, _uuid(sp_id))
    if sp is None or sp.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    from dbos import EnqueueOptions

    from jobos.workflows.runtime import client

    wf_id = f"discovery:{sp_id}:manual:{datetime.now(UTC):%Y%m%d%H%M%S}"
    opts: EnqueueOptions = {"workflow_name": "discovery_workflow", "queue_name": "discovery", "workflow_id": wf_id}
    client().enqueue(opts, sp_id, max_llm_scores)
    return {"workflow_id": wf_id}


# ------------------------------------------------------------------------------- jobs / matches --

@router.get("/jobs")
def list_jobs(status: str = "shortlisted", min_score: int = 0, q: str = "", limit: int = 100, offset: int = 0,
              auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    stmt = select(Match, Job).join(Job, Job.id == Match.job_id).where(Match.candidate_id == auth.candidate_id)
    if status != "all":
        stmt = stmt.where(Match.status.in_(status.split(",")))
    if min_score:
        stmt = stmt.where(Match.score >= min_score)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Job.title).like(like) | func.lower(Job.company_name).like(like))
    total = s.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = s.execute(stmt.order_by(Match.score.desc().nulls_last(), Job.posted_at.desc().nulls_last())
                     .limit(min(limit, 500)).offset(offset)).all()
    app_by_job = {a.job_id: a for a in s.scalars(select(Application).where(
        Application.candidate_id == auth.candidate_id, Application.job_id.in_([j.id for _, j in rows])))}
    return {"total": total, "items": [_job_row(m, j, app_by_job.get(j.id)) for m, j in rows]}


def _job_row(m: Match, j: Job, app: Application | None) -> dict[str, Any]:
    return {"match_id": str(m.id), "job_id": str(j.id), "title": j.title, "company": j.company_name,
            "locations": j.locations, "countries": j.countries, "remote_type": j.remote_type, "ats": j.ats,
            "url": j.url or j.apply_url, "apply_url": j.apply_url, "posted_at": j.posted_at, "status": m.status,
            "score": m.score, "reasons": m.reasons, "gaps": m.gaps, "eligibility": m.eligibility,
            "legitimacy": m.legitimacy, "legitimacy_reasons": m.legitimacy_reasons, "filter_reasons": m.filter_reasons,
            "seniority": j.seniority, "salary": j.salary, "feedback": m.feedback,
            "application": {"id": str(app.id), "state": app.state} if app else None}


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    j = s.get(Job, _uuid(job_id))
    if j is None:
        raise HTTPException(404)
    m = s.scalar(select(Match).where(Match.candidate_id == auth.candidate_id, Match.job_id == j.id))
    app = s.scalar(select(Application).where(Application.candidate_id == auth.candidate_id, Application.job_id == j.id))
    row = _job_row(m, j, app) if m else {"job_id": str(j.id), "title": j.title, "company": j.company_name}
    row["description"] = j.description_text
    return row


class FeedbackIn(BaseModel):
    feedback: str  # up | down
    dismiss: bool = False


@router.post("/matches/{match_id}/feedback")
def feedback(match_id: str, body: FeedbackIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    m = s.get(Match, _uuid(match_id))
    if m is None or m.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    m.feedback = body.feedback
    if body.dismiss:
        m.status = "dismissed"
    return {"ok": True}


class ApplyIn(BaseModel):
    document_id: str | None = None
    dry_run: bool = False  # fill everything, run the gate, never submit


@router.post("/jobs/{job_id}/apply")
def apply(job_id: str, body: ApplyIn | None = None, auth: AuthContext = Depends(owner),
          s: Session = Depends(db)) -> dict[str, str]:
    st = get_candidate_settings(s, auth.candidate_id)
    try:
        app = create_application(s, auth.candidate_id, _uuid(job_id), cooldown_days=st.pacing.reapply_cooldown_days)
    except DuplicateApplication as exc:
        raise HTTPException(409, str(exc)) from exc
    if body and body.document_id:
        app.document_id = _uuid(body.document_id)
    if body:
        app.dry_run = body.dry_run
    job = s.get(Job, app.job_id)
    app.workflow_id = new_workflow_id(str(app.id))  # recorded before enqueue so cancel always finds it
    s.commit()
    _enqueue(str(app.id), job.company_name if job else "", app.workflow_id)
    return {"application_id": str(app.id)}


def new_workflow_id(app_id: str) -> str:
    return f"apply:{app_id}:{uuid.uuid4().hex[:8]}"


def _enqueue(app_id: str, company: str, workflow_id: str) -> None:
    from dbos import EnqueueOptions

    from jobos.workflows.runtime import client

    opts: EnqueueOptions = {"workflow_name": "application_workflow", "queue_name": "apply",
                            "workflow_id": workflow_id, "queue_partition_key": company.lower() or "default"}
    client().enqueue(opts, app_id)


class ImportUrlIn(BaseModel):
    url: str


@router.post("/jobs/import-url")
def import_url(body: ImportUrlIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    """Paste any Greenhouse/Lever/Ashby job URL: adds the company board and crawls it (FR-DISC-5)."""
    found = detect_ats_from_url(body.url)
    if not found:
        raise HTTPException(400, "unsupported URL (Greenhouse, Lever or Ashby job links for now)")
    ats, token = found
    company = add_company(s, ats, token)
    stats = crawl_company(s, company)
    return {"company": company.name, "ats": ats, "fetched": stats.fetched, "new": stats.new, "error": stats.error}


# ----------------------------------------------------------------------------- applications --

@router.get("/applications")
def list_applications(state: str = "", limit: int = 200, auth: AuthContext = Depends(owner),
                      s: Session = Depends(db)) -> list[dict[str, Any]]:
    stmt = select(Application, Job).join(Job, Job.id == Application.job_id).where(
        Application.candidate_id == auth.candidate_id)
    if state:
        stmt = stmt.where(Application.state.in_(state.split(",")))
    rows = s.execute(stmt.order_by(Application.updated_at.desc()).limit(min(limit, 1000))).all()
    return [{"id": str(a.id), "state": a.state, "title": j.title, "company": j.company_name, "ats": j.ats,
             "apply_url": j.apply_url, "attempt": a.attempt, "error": a.error, "submitted_at": a.submitted_at,
             "updated_at": a.updated_at, "gate": a.gate, "dry_run": a.dry_run, "outcome": a.outcome} for a, j in rows]


@router.get("/applications/{app_id}")
def application_detail(app_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    a = s.get(Application, _uuid(app_id))
    if a is None or a.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    j = s.get(Job, a.job_id)
    events = s.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == a.id).order_by(ApplicationEvent.id))
    pages = s.scalars(select(FormPageRecord).where(FormPageRecord.application_id == a.id).order_by(FormPageRecord.created_at))
    cost = s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(LLMCall.ref == str(a.id)))
    emails = s.scalars(select(EmailMessage).where(EmailMessage.application_id == a.id))
    return {
        "id": str(a.id), "state": a.state, "attempt": a.attempt, "error": a.error, "gate": a.gate,
        "dry_run": a.dry_run, "outcome": a.outcome,
        "submitted_at": a.submitted_at, "llm_cost_usd": float(cost or 0),
        "job": {"id": str(j.id), "title": j.title, "company": j.company_name, "url": j.apply_url} if j else None,
        "events": [{"from": e.from_state, "to": e.to_state, "actor": e.actor, "data": e.data, "at": e.at} for e in events],
        "pages": [{"attempt": p.attempt, "page_index": p.page_index, "url": p.url, "page": p.page, "plan": p.plan,
                   "fill_result": p.fill_result, "screenshots": p.screenshots} for p in pages],
        "emails": [{"subject": e.subject, "from": e.from_addr, "category": e.category, "received_at": e.received_at,
                    "summary": (e.extracted or {}).get("summary", "")} for e in emails],
    }


@router.post("/applications/{app_id}/retry")
def retry_application(app_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    a = s.get(Application, _uuid(app_id))
    if a is None or a.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    if a.state in {st.value for st in ACTIVE}:
        raise HTTPException(409, "application is still running")
    transition(s, a, AppState.queued, actor="user", data={"reason": "retry"})
    j = s.get(Job, a.job_id)
    a.workflow_id = new_workflow_id(str(a.id))
    s.commit()
    _enqueue(str(a.id), j.company_name if j else "", a.workflow_id)
    return {"ok": True}


@router.post("/applications/{app_id}/cancel")
def cancel_application(app_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    a = s.get(Application, _uuid(app_id))
    if a is None or a.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    if a.state not in (AppState.queued, AppState.in_progress, AppState.needs_input, AppState.ready_for_review):
        raise HTTPException(409, f"cannot cancel in state {a.state}")
    wf = a.workflow_id
    transition(s, a, AppState.cancelled, actor="user")
    rg.cancel_pending_for_workflow(s, wf)
    for iv in s.scalars(select(Intervention).where(Intervention.application_id == a.id, Intervention.status == "open")):
        iv.status = "cancelled"
    s.commit()
    if wf:
        from jobos.workflows.runtime import client

        try:
            client().cancel_workflow(wf)
        except Exception:
            pass
    return {"ok": True}


# ----------------------------------------------------------------------------- interventions --

@router.get("/interventions")
def list_interventions(status: str = "open", auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    stmt = select(Intervention).where(Intervention.candidate_id == auth.candidate_id)
    if status != "all":
        stmt = stmt.where(Intervention.status == status)
    return [_iv(i) for i in s.scalars(stmt.order_by(Intervention.created_at.desc()).limit(200))]


def _iv(i: Intervention) -> dict[str, Any]:
    return {"id": str(i.id), "kind": i.kind, "title": i.title, "status": i.status, "payload": i.payload,
            "answer": i.answer, "application_id": str(i.application_id) if i.application_id else None,
            "created_at": i.created_at, "expires_at": i.expires_at}


@router.get("/interventions/{iv_id}")
def get_intervention(iv_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    i = s.get(Intervention, _uuid(iv_id))
    if i is None or i.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    return _iv(i)


class AnswerIn(BaseModel):
    answers: dict[str, Any] = {}
    remember: dict[str, str] = {}  # key -> global | company | job | none
    decision: str | None = None  # approve | reject (review)
    done: bool | None = None  # login/captcha


@router.post("/interventions/{iv_id}/answer")
def answer(iv_id: str, body: AnswerIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    i = s.get(Intervention, _uuid(iv_id))
    if i is None or i.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    payload = body.model_dump(exclude_none=True)
    iv = iv_svc.answer_intervention(s, i.id, payload, via="web")
    if iv is None:
        raise HTTPException(409, "intervention is not open")
    wf, topic = iv.workflow_id, iv.topic
    s.commit()
    signal_workflow(wf, payload, topic)
    return {"ok": True}


def signal_workflow(workflow_id: str, message: dict[str, Any], topic: str) -> None:
    from jobos.workflows.runtime import client

    client().send(workflow_id, message, topic)


# ------------------------------------------------------------------------------- answer bank --

@router.get("/answers")
def list_answers(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    rows = s.scalars(select(Answer).where(Answer.candidate_id == auth.candidate_id).order_by(Answer.updated_at.desc()))
    return [{"id": str(a.id), "question": a.question, "value": a.value, "options": a.options, "scope": a.scope,
             "scope_ref": a.scope_ref, "source": a.source, "use_count": a.use_count} for a in rows]


class AnswerBankIn(BaseModel):
    question: str
    value: Any
    scope: str = "global"
    scope_ref: str = ""


@router.post("/answers")
def add_answer(body: AnswerBankIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, str]:
    a = save_answer(s, auth.candidate_id, body.question, body.value, scope=body.scope, scope_ref=body.scope_ref)
    return {"id": str(a.id)}


@router.delete("/answers/{answer_id}")
def delete_answer(answer_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    a = s.get(Answer, _uuid(answer_id))
    if a is None or a.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    s.delete(a)
    return {"deleted": True}


# ------------------------------------------------------------------------- companies / runners --

@router.get("/companies")
def list_companies(s: Session = Depends(db), auth: AuthContext = Depends(owner)) -> list[dict[str, Any]]:
    counts = dict(s.execute(select(Job.company_id, func.count()).where(Job.closed_at.is_(None)).group_by(Job.company_id)).all())
    return [{"id": str(c.id), "name": c.name, "ats": c.ats, "board_token": c.board_token, "enabled": c.enabled,
             "open_jobs": counts.get(c.id, 0), "last_crawled_at": c.last_crawled_at, "last_error": c.last_error}
            for c in s.scalars(select(Company).order_by(Company.name))]


class CompanyIn(BaseModel):
    ats: str
    board_token: str
    name: str = ""


@router.post("/companies")
def create_company(body: CompanyIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, str]:
    c = add_company(s, body.ats, body.board_token, body.name)
    return {"id": str(c.id)}


@router.get("/runners")
def list_runners(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    return [{"id": str(r.id), "name": r.name, "version": r.version, "os": r.os, "revoked": r.revoked,
             "last_seen_at": r.last_seen_at,
             "online": bool(r.last_seen_at and now - r.last_seen_at < timedelta(seconds=90))}
            for r in s.scalars(select(Runner).where(Runner.candidate_id == auth.candidate_id))]


class RunnerIn(BaseModel):
    name: str


@router.post("/runners")
def create_runner(body: RunnerIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, str]:
    r, token = rg.create_runner(s, auth.candidate_id, body.name)
    return {"id": str(r.id), "token": token}


@router.delete("/runners/{runner_id}")
def revoke_runner(runner_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    r = s.get(Runner, _uuid(runner_id))
    if r is None or r.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    r.revoked = True
    return {"ok": True}


# --------------------------------------------------------------------------------- mailboxes --

class MailboxIn(BaseModel):
    label: str
    provider: str = "gmail"  # gmail | zoho | zoho_com | outlook | custom
    username: str
    app_password: str
    host: str = ""
    port: int = 993


@router.get("/mailboxes")
def list_mailboxes(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> list[dict[str, Any]]:
    return [{"id": str(m.id), "label": m.label, "host": m.host, "username": m.username, "enabled": m.enabled,
             "last_sync_at": m.last_sync_at, "last_error": m.last_error}
            for m in s.scalars(select(Mailbox).where(Mailbox.candidate_id == auth.candidate_id))]


@router.post("/mailboxes")
def add_mailbox(body: MailboxIn, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, str]:
    host, port = PRESETS.get(body.provider, (body.host, body.port))
    if not host:
        raise HTTPException(400, "host required for custom provider")
    m = Mailbox(candidate_id=auth.candidate_id, label=body.label, host=host, port=port, username=body.username,
                secret_enc=encrypt(body.app_password))
    s.add(m)
    s.flush()
    return {"id": str(m.id)}


@router.delete("/mailboxes/{mb_id}")
def delete_mailbox(mb_id: str, auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, bool]:
    m = s.get(Mailbox, _uuid(mb_id))
    if m is None or m.candidate_id != auth.candidate_id:
        raise HTTPException(404)
    s.delete(m)
    return {"deleted": True}


# ------------------------------------------------------------------------------- stats / files --

@router.get("/stats")
def stats(auth: AuthContext = Depends(owner), s: Session = Depends(db)) -> dict[str, Any]:
    by_state = dict(s.execute(select(Application.state, func.count()).where(
        Application.candidate_id == auth.candidate_id).group_by(Application.state)).all())
    by_match = dict(s.execute(select(Match.status, func.count()).where(
        Match.candidate_id == auth.candidate_id).group_by(Match.status)).all())
    since = datetime.now(UTC) - timedelta(days=1)
    cost_today = s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(LLMCall.created_at >= since))
    cost_total = s.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0)))
    open_iv = s.scalar(select(func.count()).select_from(Intervention).where(
        Intervention.candidate_id == auth.candidate_id, Intervention.status == "open"))
    jobs_open = s.scalar(select(func.count()).select_from(Job).where(Job.closed_at.is_(None)))
    return {"applications": by_state, "matches": by_match, "open_interventions": open_iv, "open_jobs": jobs_open,
            "llm_cost_24h": float(cost_today or 0), "llm_cost_total": float(cost_total or 0),
            "llm_budget_24h": get_settings().llm_daily_budget_usd}


@router.get("/files/{path:path}")
def get_file(path: str, auth: AuthContext = Depends(owner)) -> FileResponse:
    if not path.startswith("evidence/") or ".." in path:
        raise HTTPException(404)
    full = (get_settings().data_dir / path).resolve()
    if not str(full).startswith(str(get_settings().data_dir.resolve())) or not full.exists():
        raise HTTPException(404)
    return FileResponse(full)
