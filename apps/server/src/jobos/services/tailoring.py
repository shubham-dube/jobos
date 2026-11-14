"""Tailored documents per job (spec 0002): generate once, store with provenance, reuse."""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobos.db.models import Document, Job
from jobos.domain.settings import TailoringSettings
from jobos.llm import LLMGateway
from jobos.services.candidates import get_profile
from jobos.services.storage import put_bytes, sha256
from jobos.tailoring.cover_letter import write_cover_letter
from jobos.tailoring.render import paper_for, pdf_text, render_cover_letter, render_resume
from jobos.tailoring.tailor import tailor_resume

log = structlog.get_logger(__name__)

TAILORED = "tailored_resume"
COVER = "cover_letter"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40] or "Company"


def job_document(s: Session, candidate_id: uuid.UUID, job_id: uuid.UUID, generator: str) -> Document | None:
    return s.scalar(select(Document).where(Document.candidate_id == candidate_id, Document.job_id == job_id,
                                           Document.meta["generator"].astext == generator)
                    .order_by(Document.created_at.desc()))


def _store(s: Session, candidate_id: uuid.UUID, job: Job, *, kind: str, label: str, filename: str, pdf: bytes,
           meta: dict[str, Any]) -> Document:
    doc_id = uuid.uuid4()
    path = put_bytes(f"documents/{candidate_id}/{doc_id}/{filename}", pdf)
    d = Document(id=doc_id, candidate_id=candidate_id, kind=kind, label=label[:120], filename=filename,
                 content_type="application/pdf", storage_path=path, sha256=sha256(pdf), text=pdf_text(pdf)[:50000],
                 is_default=False, job_id=job.id, meta=meta)
    s.add(d)
    s.flush()
    return d


def tailor_for_job(s: Session, gateway: LLMGateway | None, candidate_id: uuid.UUID, job_id: uuid.UUID, *,
                   settings: TailoringSettings | None = None, force: bool = False, ref: str = "") -> Document:
    """Return this job's tailored resume, generating it if needed (one LLM call + optional verify)."""
    cfg = settings or TailoringSettings()
    if not force:
        existing = job_document(s, candidate_id, job_id, TAILORED)
        if existing is not None:
            return existing
    job = s.get(Job, job_id)
    if job is None:
        raise LookupError("job not found")
    profile = get_profile(s, candidate_id)
    result = tailor_resume(gateway, profile, title=job.title, company=job.company_name,
                           description=job.description_text or "", rephrase=cfg.rephrase, verify=cfg.verify,
                           ref=ref or f"job:{job_id}")
    paper = paper_for(job.countries)
    out = render_resume(profile, result.variant, paper=paper, max_pages=cfg.max_pages)
    meta = {
        "generator": TAILORED, "job_title": job.title, "company": job.company_name, "paper": paper,
        "pages": out.pages, "trimmed": out.trimmed, "used_llm": result.used_llm, "keywords": result.keywords,
        "variant": out.variant.model_dump(mode="json"), "diff": [d.model_dump(mode="json") for d in result.diff],
        "grounding": result.grounding.model_dump(mode="json"),
    }
    name = profile.basics.full_name.replace(" ", "_") or "Resume"
    doc = _store(s, candidate_id, job, kind="resume", label=f"Tailored · {job.company_name}",
                 filename=f"{name}_Resume_{_slug(job.company_name)}.pdf", pdf=out.pdf, meta=meta)
    log.info("tailor.done", job=str(job_id), reworded=result.grounding.reworded, rejected=result.grounding.rejected,
             pages=out.pages)
    return doc


def cover_letter_for_job(s: Session, gateway: LLMGateway, candidate_id: uuid.UUID, job_id: uuid.UUID, *,
                         force: bool = False, ref: str = "") -> Document | None:
    """Grounded cover letter for this job, or None if too little survived grounding (→ ask the user)."""
    if not force:
        existing = job_document(s, candidate_id, job_id, COVER)
        if existing is not None:
            return existing
    job = s.get(Job, job_id)
    if job is None:
        raise LookupError("job not found")
    profile = get_profile(s, candidate_id)
    res = write_cover_letter(gateway, profile, title=job.title, company=job.company_name,
                             description=job.description_text or "", ref=ref or f"job:{job_id}")
    if not res.ok:
        log.warning("cover_letter.rejected", job=str(job_id), kept=res.kept, dropped=len(res.dropped))
        return None
    pdf = render_cover_letter(profile, res.paragraphs, company=job.company_name, greeting=res.letter.greeting,
                              closing=res.letter.closing, paper=paper_for(job.countries))
    name = profile.basics.full_name.replace(" ", "_") or "Cover_Letter"
    return _store(s, candidate_id, job, kind="cover_letter", label=f"Cover letter · {job.company_name}",
                  filename=f"{name}_Cover_Letter_{_slug(job.company_name)}.pdf", pdf=pdf,
                  meta={"generator": COVER, "job_title": job.title, "company": job.company_name,
                        "paragraphs": res.paragraphs, "dropped": res.dropped, "kept": res.kept,
                        "letter": res.letter.model_dump(mode="json")})


def document_summary(d: Document) -> dict[str, Any]:
    m = d.meta or {}
    g = m.get("grounding") or {}
    return {"id": str(d.id), "kind": d.kind, "label": d.label, "filename": d.filename,
            "job_id": str(d.job_id) if d.job_id else None, "generator": m.get("generator", ""),
            "reworded": g.get("reworded", 0), "rejected": g.get("rejected", 0), "pages": m.get("pages")}
