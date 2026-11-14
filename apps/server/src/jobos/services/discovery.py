"""Discovery pipeline: crawl ATS boards → upsert jobs → filter/eligibility/legitimacy → LLM score."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from jobos.db.models import Company, Document, Job, Match, SearchProfile
from jobos.domain.settings import SearchFilters
from jobos.llm import BudgetExceeded, LLMGateway
from jobos.matching.rules import (
    Eligibility,
    application_deadline,
    apply_filters,
    assess_eligibility,
    legitimacy,
    prescore,
)
from jobos.matching.scorer import candidate_summary, score_job
from jobos.services.candidates import get_profile
from jobos.sources.ats import SOURCES, SourceError
from jobos.sources.base import NormalizedJob, normalize_company, normalize_title

log = structlog.get_logger(__name__)


def seed_companies(s: Session) -> int:
    data = json.loads(resources.files("jobos.sources").joinpath("seed_companies.json").read_text())
    before = s.scalar(select(func.count()).select_from(Company)) or 0
    for row in data:
        stmt = insert(Company).values(
            id=uuid.uuid4(), name=row["name"], normalized_name=normalize_company(row["name"]), ats=row["ats"],
            board_token=row["board_token"], enabled=True, created_at=datetime.now(UTC),
            domain="", tier="", last_error="",
        ).on_conflict_do_nothing(index_elements=["ats", "board_token"])
        s.execute(stmt)
    return (s.scalar(select(func.count()).select_from(Company)) or 0) - before


def add_company(s: Session, ats: str, board_token: str, name: str = "") -> Company:
    existing = s.scalar(select(Company).where(Company.ats == ats, Company.board_token == board_token))
    if existing:
        return existing
    c = Company(name=name or board_token, normalized_name=normalize_company(name or board_token), ats=ats,
                board_token=board_token)
    s.add(c)
    s.flush()
    return c


def add_found_boards(s: Session, found: list[Any]) -> list[str]:
    """Add boards found by board discovery; returns names of newly added companies."""
    added: list[str] = []
    for f in found:
        if s.scalar(select(Company).where(Company.ats == f.ats, Company.board_token == f.board_token)):
            continue
        add_company(s, f.ats, f.board_token, f.name)
        added.append(f"{f.name} ({f.ats})")
    return added


def import_single_form(s: Session, posting: Any, company_name: str = "") -> Job:
    """A Google Form (or other single application page) as a job. Idempotent per form."""
    name = company_name.strip() or posting.title
    company = add_company(s, posting.ats, posting.form_id, name)
    company.enabled = False  # nothing to crawl: the form is the posting
    existing = s.scalar(select(Job).where(Job.source == posting.ats, Job.source_job_id == posting.form_id))
    if existing:
        return existing
    nj = NormalizedJob(source=posting.ats, source_job_id=posting.form_id, company_name=name, title=posting.title,
                       board_token=posting.form_id,
                       url=posting.url, apply_url=posting.url, ats=posting.ats,
                       description_text=posting.description, raw={"single_form": True})
    job = Job(company_id=company.id, company_name=name, source=nj.source, source_job_id=nj.source_job_id,
              url=nj.url, apply_url=nj.apply_url, ats=nj.ats, title=nj.title, title_norm=nj.title_norm,
              locations=[], countries=[], remote_type="unknown", employment_type="", seniority="", salary=None,
              description_text=nj.description_text, posted_at=datetime.now(UTC), fingerprint=nj.fingerprint,
              raw=nj.raw)
    s.add(job)
    s.flush()
    return job


@dataclass
class CrawlStats:
    fetched: int = 0
    new: int = 0
    closed: int = 0
    error: str = ""


def upsert_jobs(s: Session, company: Company, jobs: list[NormalizedJob]) -> CrawlStats:
    stats = CrawlStats(fetched=len(jobs))
    now = datetime.now(UTC)
    seen_ids: set[str] = set()
    for j in jobs:
        seen_ids.add(j.source_job_id)
        # Board data is external: clamp to the column sizes so one odd posting can't fail the whole board.
        values = dict(
            company_id=company.id, company_name=j.company_name[:200], source=j.source[:30],
            source_job_id=j.source_job_id[:200], url=j.url, apply_url=j.apply_url, ats=j.ats[:30], title=j.title[:300],
            title_norm=j.title_norm[:300], department=j.department[:200], locations=j.locations, countries=j.countries,
            remote_type=j.remote_type[:20], employment_type=j.employment_type[:30], seniority="", salary=j.salary, description_text=j.description_text,
            posted_at=j.posted_at, last_seen_at=now, closed_at=None, fingerprint=j.fingerprint, raw=j.raw,
        )
        stmt = insert(Job).values(id=uuid.uuid4(), first_seen_at=now, **values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "source_job_id"],
            set_={k: stmt.excluded[k] for k in ("title", "title_norm", "locations", "countries", "remote_type",
                                               "description_text", "last_seen_at", "closed_at", "apply_url",
                                               "salary", "raw")},
        ).returning(Job.first_seen_at)
        first_seen = s.execute(stmt).scalar_one()
        if first_seen == now:
            stats.new += 1
    # jobs that disappeared from the board are closed
    if jobs:
        res = s.execute(
            update(Job)
            .where(Job.company_id == company.id, Job.closed_at.is_(None), Job.source_job_id.not_in(seen_ids))
            .values(closed_at=now)
        )
        stats.closed = res.rowcount or 0
    company.last_crawled_at = now
    company.last_error = ""
    if jobs and company.name == company.board_token:
        company.name = jobs[0].company_name
    return stats


def crawl_company(s: Session, company: Company) -> CrawlStats:
    source_cls = SOURCES.get(company.ats)
    if source_cls is None:
        return CrawlStats(error=f"unsupported ats {company.ats}")
    try:
        jobs = source_cls().fetch(company.board_token, company.name)
    except SourceError as exc:
        company.last_error = str(exc)[:500]
        if exc.not_found:
            company.enabled = False
        return CrawlStats(error=str(exc))
    return upsert_jobs(s, company, jobs)


@dataclass
class EvalStats:
    considered: int = 0
    filtered: int = 0
    scored: int = 0
    shortlisted: int = 0
    skipped_budget: int = 0
    errors: list[str] = field(default_factory=list)


def evaluate_jobs(s: Session, gateway: LLMGateway | None, search_profile: SearchProfile, *,
                  max_llm_scores: int = 50, min_score_shortlist: int = 60) -> EvalStats:
    """Create/refresh matches for open jobs not yet evaluated for this candidate."""
    stats = EvalStats()
    filters = SearchFilters.model_validate(search_profile.filters or {})
    cand_id = search_profile.candidate_id
    profile = get_profile(s, cand_id)
    labels = [d.label for d in s.scalars(select(Document).where(Document.candidate_id == cand_id,
                                                                Document.kind == "resume")) if d.label]
    summary = candidate_summary(profile, labels)

    already = select(Match.job_id).where(Match.candidate_id == cand_id)
    jobs = s.scalars(
        select(Job).where(Job.closed_at.is_(None), Job.id.not_in(already), Job.ats.in_(filters.sources))
        .order_by(Job.posted_at.desc().nulls_last()).limit(50000)
    ).all()
    to_score: list[tuple[float, Job, Match]] = []
    seen_fp = set(s.scalars(select(Job.fingerprint).join(Match, Match.job_id == Job.id)
                            .where(Match.candidate_id == cand_id)))
    targets = profile.preferences.target_roles or filters.keywords_any
    for job in jobs:
        stats.considered += 1
        if (job.raw or {}).get("needs_hydrate"):
            pre = apply_filters(filters, title=job.title, company=job.company_name, countries=job.countries,
                                remote_type=job.remote_type, posted_at=job.posted_at,
                                eligibility=Eligibility(True, "unknown"))
            if pre.passed:
                hydrate_job(s, job)
        elig = assess_eligibility(profile, job.countries, job.remote_type, job.description_text, job.locations)
        fr = apply_filters(filters, title=job.title, company=job.company_name, countries=job.countries,
                           remote_type=job.remote_type, posted_at=job.posted_at, eligibility=elig,
                           deadline=application_deadline(job.description_text))
        job.seniority = fr.seniority
        legit, legit_reasons = legitimacy(source=job.source, ats=job.ats, posted_at=job.posted_at,
                                          description=job.description_text)
        duplicate = job.fingerprint in seen_fp
        seen_fp.add(job.fingerprint)
        if duplicate:
            fr.passed, fr.reasons = False, [*fr.reasons, "duplicate of another posting"]
        m = Match(candidate_id=cand_id, job_id=job.id, search_profile_id=search_profile.id,
                  status="new" if fr.passed else "filtered", filter_reasons=fr.reasons,
                  eligibility={"eligible": elig.eligible, "status": elig.status, "reasons": elig.reasons},
                  legitimacy=legit, legitimacy_reasons=legit_reasons)
        s.add(m)
        if fr.passed:
            to_score.append((prescore(job.title, targets, elig.status, legit, profile.is_student()), job, m))
        else:
            stats.filtered += 1
    s.flush()

    # Matches that passed the filters earlier but were never scored (budget or cap reached on that run)
    pending = s.execute(select(Match, Job).join(Job, Job.id == Match.job_id).where(
        Match.candidate_id == cand_id, Match.status == "new", Match.score.is_(None), Job.closed_at.is_(None))).all()
    queued_ids = {m.id for _, _, m in to_score}
    for m, job in pending:
        if m.id not in queued_ids:
            to_score.append((prescore(job.title, targets, (m.eligibility or {}).get("status", ""), m.legitimacy or 0,
                                      profile.is_student()), job, m))

    to_score.sort(key=lambda t: -t[0])
    for _, job, m in to_score:
        if gateway is None or stats.scored >= max_llm_scores:
            stats.skipped_budget += 1
            continue
        try:
            v = score_job(gateway, summary, title=job.title, company=job.company_name, locations=job.locations,
                          eligibility=f"{m.eligibility['status']}: {'; '.join(m.eligibility['reasons'])}",
                          description=job.description_text, ref=f"job:{job.id}")
        except BudgetExceeded:  # daily budget used up: the rest are scored on a later run
            stats.skipped_budget += 1
            gateway = None
            continue
        except Exception as exc:  # one bad job must not stop the batch
            if len(stats.errors) < 20:
                stats.errors.append(f"{job.id}: {exc}")
            log.warning("match.score_failed", job=str(job.id), error=str(exc))
            continue
        m.score, m.reasons, m.gaps = v.score, v.reasons, v.gaps
        m.resume_label = v.resume_label if v.resume_label in labels else ""
        m.scored_at = datetime.now(UTC)
        m.status = "shortlisted" if v.score >= min_score_shortlist else "scored"
        stats.scored += 1
        stats.shortlisted += m.status == "shortlisted"
    search_profile.last_run_at = datetime.now(UTC)
    return stats


def title_similar(a: str, b: str) -> bool:
    from rapidfuzz import fuzz

    return fuzz.token_set_ratio(normalize_title(a), normalize_title(b)) >= 90


def hydrate_job(s: Session, job: Job) -> bool:
    """Fetch the full description for sources whose list API omits it (Workday, SmartRecruiters, Workable)."""
    source_cls = SOURCES.get(job.source)
    company = s.get(Company, job.company_id) if job.company_id else None
    if source_cls is None or company is None or not hasattr(source_cls, "hydrate"):
        return False
    try:
        extra = source_cls().hydrate(company.board_token, job.raw or {})  # type: ignore[attr-defined]
    except Exception as exc:
        log.warning("hydrate_failed", job=str(job.id), error=str(exc))
        return False
    for key, value in extra.items():
        if value:
            setattr(job, key, value)
    job.raw = {**(job.raw or {}), "needs_hydrate": False}
    return True
