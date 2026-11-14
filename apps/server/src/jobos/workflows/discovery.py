"""Discovery workflows: crawl boards, evaluate matches, auto-queue applications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from dbos import DBOS, SetWorkflowID
from sqlalchemy import func, select

from jobos.db import session_scope
from jobos.db.models import Application, Company, Job, Match, SearchProfile
from jobos.llm import get_gateway
from jobos.services.applications import DuplicateApplication, create_application
from jobos.services.candidates import get_candidate_settings
from jobos.services.discovery import crawl_company, evaluate_jobs

log = structlog.get_logger(__name__)
RECRAWL_AFTER = timedelta(hours=3)


@DBOS.step()
def companies_due_step() -> list[str]:
    cutoff = datetime.now(UTC) - RECRAWL_AFTER
    with session_scope() as s:
        return [str(c.id) for c in s.scalars(select(Company).where(
            Company.enabled.is_(True),
            (Company.last_crawled_at.is_(None)) | (Company.last_crawled_at < cutoff)))]


@DBOS.step()
def crawl_step(company_id: str) -> dict[str, Any]:
    """Crawl one board. Never raises: a broken board is recorded on the company and retried on a later run,
    so one employer can't stop discovery for everyone else."""
    try:
        with session_scope() as s:
            c = s.get(Company, uuid.UUID(company_id))
            if c is None:
                return {}
            st = crawl_company(s, c)
            return {"company": c.name, "fetched": st.fetched, "new": st.new, "closed": st.closed, "error": st.error}
    except Exception as exc:
        log.warning("crawl.failed", company=company_id, error=str(exc)[:300])
        with session_scope() as s:
            c = s.get(Company, uuid.UUID(company_id))
            if c is not None:
                c.last_error = f"{type(exc).__name__}: {exc}"[:500]
                c.last_crawled_at = datetime.now(UTC)  # back off until the next recrawl window
        return {"error": str(exc)[:300]}


@DBOS.step()
def evaluate_step(search_profile_id: str, max_llm_scores: int) -> dict[str, Any]:
    with session_scope() as s:
        sp = s.get(SearchProfile, uuid.UUID(search_profile_id))
        if sp is None:
            return {}
        st = get_candidate_settings(s, sp.candidate_id)
        stats = evaluate_jobs(s, get_gateway(), sp, max_llm_scores=max_llm_scores,
                              min_score_shortlist=st.thresholds.min_match_score_to_queue)
        return stats.__dict__


@DBOS.step()
def auto_queue_step(search_profile_id: str) -> list[tuple[str, str, str]]:
    """Create applications for shortlisted matches (auto_apply profiles). Returns (app_id, company)."""
    out: list[tuple[str, str, str]] = []
    with session_scope() as s:
        sp = s.get(SearchProfile, uuid.UUID(search_profile_id))
        if sp is None or not sp.auto_apply:
            return out
        st = get_candidate_settings(s, sp.candidate_id)
        # daily cap over a rolling 24h window, shared by every profile/run of this candidate
        created = s.scalar(select(func.count()).select_from(Application).where(
            Application.candidate_id == sp.candidate_id,
            Application.created_at >= datetime.now(UTC) - timedelta(hours=24))) or 0
        room = max(st.pacing.daily_cap - created, 0)
        if room == 0:
            log.info("auto_queue.daily_cap_reached", cap=st.pacing.daily_cap)
            return out
        rows = s.execute(select(Match, Job).join(Job, Job.id == Match.job_id).where(
            Match.candidate_id == sp.candidate_id, Match.status == "shortlisted",
            Match.score >= st.thresholds.min_match_score_to_queue,
            Match.legitimacy >= st.thresholds.min_legitimacy_to_queue, Job.closed_at.is_(None),
        ).order_by(Match.score.desc()).limit(room)).all()
        for m, job in rows:
            try:
                app = create_application(s, sp.candidate_id, job.id, cooldown_days=st.pacing.reapply_cooldown_days,
                                         actor="auto")
            except DuplicateApplication:
                m.status = "scored"
                continue
            m.status = "queued"
            app.workflow_id = f"apply:{app.id}:{uuid.uuid4().hex[:8]}"
            out.append((str(app.id), job.company_name, app.workflow_id))
    return out


@DBOS.workflow()
def discovery_workflow(search_profile_id: str, max_llm_scores: int = 500, crawl: bool = True) -> dict[str, Any]:
    """Crawl due boards (optional), evaluate/score new jobs, auto-queue. Scoring runs on the cheap ``job`` route
    (≈ $0.0006/job on Haiku), so the default scores up to 500 jobs per run."""
    summary: dict[str, Any] = {"crawled": 0, "new_jobs": 0, "errors": 0}
    for cid in companies_due_step() if crawl else []:
        r = crawl_step(cid)
        summary["crawled"] += 1
        summary["new_jobs"] += r.get("new", 0)
        summary["errors"] += bool(r.get("error"))
    summary["evaluation"] = evaluate_step(search_profile_id, max_llm_scores)
    from .application import enqueue_application

    queued = auto_queue_step(search_profile_id)
    for app_id, company, wf_id in queued:
        enqueue_application(app_id, company, wf_id)
    summary["queued"] = len(queued)
    return summary


@DBOS.step(retries_allowed=True, max_attempts=2, interval_seconds=30)
def probe_boards_step(names: list[str]) -> list[dict[str, Any]]:
    from jobos.sources.board_discovery import discover

    return [f.__dict__ for f in discover(names)]


@DBOS.step()
def add_boards_step(found: list[dict[str, Any]]) -> list[str]:
    from jobos.services.discovery import add_found_boards
    from jobos.sources.board_discovery import Found

    with session_scope() as s:
        return add_found_boards(s, [Found(**f) for f in found])


@DBOS.workflow()
def board_discovery_workflow(names: list[str] | None = None, batch: int = 20) -> dict[str, Any]:
    """Probe employer names for public Greenhouse/Lever/Ashby boards and add them to the crawl list.
    Durable and resumable: each batch is a step, so a restart continues where it stopped."""
    from jobos.sources.board_discovery import candidate_names

    todo = names or candidate_names()
    added: list[str] = []
    for i in range(0, len(todo), batch):
        added += add_boards_step(probe_boards_step(todo[i:i + batch]))
    log.info("board_discovery.done", probed=len(todo), added=len(added))
    return {"probed": len(todo), "added": len(added), "companies": added}


@DBOS.step()
def due_search_profiles_step() -> list[str]:
    now = datetime.now(UTC)
    with session_scope() as s:
        return [str(sp.id) for sp in s.scalars(select(SearchProfile).where(SearchProfile.enabled.is_(True)))
                if sp.last_run_at is None or sp.last_run_at + timedelta(minutes=sp.schedule_minutes) <= now]


@DBOS.workflow()
def discovery_tick(scheduled_time: datetime, context: Any) -> None:
    for sp_id in due_search_profiles_step():
        slot = scheduled_time.strftime("%Y%m%d%H%M")
        with SetWorkflowID(f"discovery:{sp_id}:{slot}"):
            DBOS.start_workflow(discovery_workflow, sp_id)
