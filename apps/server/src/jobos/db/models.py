"""Relational schema (see docs/architecture/data-model.md).

Global (non-PII) tables: companies, jobs, site_recipes.
Candidate-scoped tables carry ``candidate_id``; candidates carry ``org_id`` (multi-tenant ready).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --------------------------------------------------------------------------------- tenancy ----

class Org(TimestampMixin, Base):
    __tablename__ = "orgs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    # CandidateSettings JSON (approval rules, caps, hours, notification prefs) - see domain/settings.py
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    current_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --------------------------------------------------------------------------------- profile ----

class ProfileVersion(TimestampMixin, Base):
    __tablename__ = "profile_versions"
    __table_args__ = (UniqueConstraint("candidate_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)  # MasterProfile
    source: Mapped[str] = mapped_column(String(50), default="manual")  # import | manual | api


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="resume")  # resume | cover_letter | other
    label: Mapped[str] = mapped_column(String(120), default="")  # e.g. "Backend", "AI Engineer"
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    storage_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Answer(TimestampMixin, Base):
    """Answer bank entry (FR-ANS-*)."""

    __tablename__ = "answers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    question_norm: Mapped[str] = mapped_column(Text, index=True)
    field_type: Mapped[str] = mapped_column(String(30), default="text")
    options: Mapped[list[str]] = mapped_column(JSONB, default=list)
    value: Mapped[Any] = mapped_column(JSONB)  # str | list[str] | bool
    scope: Mapped[str] = mapped_column(String(20), default="global")  # global | company | job
    scope_ref: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(30), default="user")
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------------------- discovery ----

class SearchProfile(TimestampMixin, Base):
    __tablename__ = "search_profiles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # SearchFilters
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)  # queue applications for matches
    schedule_minutes: Mapped[int] = mapped_column(Integer, default=360)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("ats", "board_token"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    ats: Mapped[str] = mapped_column(String(30))  # greenhouse | lever | ashby | ...
    board_token: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(200), default="")
    tier: Mapped[str] = mapped_column(String(20), default="")  # optional quality tier label
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_job_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(30))
    source_job_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    apply_url: Mapped[str] = mapped_column(Text)
    ats: Mapped[str] = mapped_column(String(30), default="unknown")
    title: Mapped[str] = mapped_column(String(300))
    title_norm: Mapped[str] = mapped_column(String(300), index=True)
    department: Mapped[str] = mapped_column(String(200), default="")
    locations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    countries: Mapped[list[str]] = mapped_column(JSONB, default=list)  # ISO2 guesses
    remote_type: Mapped[str] = mapped_column(String(20), default="unknown")  # remote|hybrid|onsite|unknown
    employment_type: Mapped[str] = mapped_column(String(30), default="")
    seniority: Mapped[str] = mapped_column(String(30), default="")
    salary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    description_text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    search_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_profiles.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|filtered|scored|shortlisted|dismissed
    filter_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    eligibility: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    legitimacy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legitimacy_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    resume_label: Mapped[str] = mapped_column(String(120), default="")
    feedback: Mapped[str] = mapped_column(String(20), default="")  # up | down
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ----------------------------------------------------------------------------- applications ----

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(30), index=True)
    workflow_id: Mapped[str] = mapped_column(String(200), default="")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # last gate decision
    error: Mapped[str] = mapped_column(Text, default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_state: Mapped[str] = mapped_column(String(30), default="")
    to_state: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(30), default="system")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FormPageRecord(Base):
    """Evidence: every page seen, the plan used, and what was read back."""

    __tablename__ = "form_pages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    page_index: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    page: Mapped[dict[str, Any]] = mapped_column(JSONB)  # FormPage
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)  # FillPlan
    fill_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    screenshots: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Intervention(Base):
    __tablename__ = "interventions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id"), nullable=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(200))  # DBOS recv topic the workflow waits on
    kind: Mapped[str] = mapped_column(String(40))  # InterventionKind
    title: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|answered|expired|cancelled
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    answered_via: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------------- runners ----

class Runner(TimestampMixin, Base):
    __tablename__ = "runners"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    version: Mapped[str] = mapped_column(String(40), default="")
    os: Mapped[str] = mapped_column(String(80), default="")
    max_sessions: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RunnerTaskRecord(Base):
    __tablename__ = "runner_tasks"
    __table_args__ = (Index("ix_runner_tasks_pending", "candidate_id", "status", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    runner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runners.id"), nullable=True)
    workflow_id: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))
    session_id: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timeout_s: Mapped[int] = mapped_column(Integer, default=180)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|leased|done|expired
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteRecipe(Base):
    """Learned site knowledge (ADR-0014). Declarative data only."""

    __tablename__ = "site_recipes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    site_key: Mapped[str] = mapped_column(String(300), unique=True)
    ats: Mapped[str] = mapped_column(String(30), default="unknown")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="learning")  # learning|active|demoted
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------------- llm / mail / misc ----

class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task: Mapped[str] = mapped_column(String(60), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(Text, default="")
    ref: Mapped[str] = mapped_column(String(200), default="", index=True)  # e.g. application id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Mailbox(TimestampMixin, Base):
    __tablename__ = "mailboxes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120))  # e.g. "Gmail", "Zoho"
    kind: Mapped[str] = mapped_column(String(20), default="imap")
    host: Mapped[str] = mapped_column(String(200))
    port: Mapped[int] = mapped_column(Integer, default=993)
    username: Mapped[str] = mapped_column(String(200))
    secret_enc: Mapped[str] = mapped_column(Text)  # encrypted app password
    folder: Mapped[str] = mapped_column(String(120), default="INBOX")
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("mailbox_id", "message_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(String(500))
    from_addr: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="", index=True)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interventions.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(300), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="sent")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200), default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
