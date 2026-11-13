"""LLM fit scoring (Matcher agent)."""

from __future__ import annotations

from jobos_common.profile import MasterProfile
from pydantic import BaseModel, Field

from jobos.llm import LLMGateway, untrusted


class MatchVerdict(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall fit 0-100")
    seniority_fit: str = Field(description="under | good | over")
    reasons: list[str] = Field(description="Top 2-4 concrete reasons this is a fit", max_length=5)
    gaps: list[str] = Field(description="Top 0-3 requirements the candidate clearly lacks", max_length=4)
    resume_label: str = Field(description="Which of the candidate's resume variants fits best (exact label) or ''")


SYSTEM = """You are the Matcher agent of a job-search assistant. Score how well ONE job fits ONE candidate.
Be calibrated and honest:
- 85-100: strong fit, candidate meets nearly all must-haves at the right level.
- 65-84: good fit, a few gaps that a strong application can overcome.
- 40-64: stretch.
- 0-39: poor fit (wrong field, far too senior, hard requirements missing).
Judge seniority against the candidate's real experience (internships count, but they are a student/new grad if so).
Never invent candidate skills; use only the candidate summary provided."""


def candidate_summary(p: MasterProfile, resume_labels: list[str]) -> str:
    lines = [
        f"Name: {p.basics.full_name}. Headline: {p.basics.headline}",
        f"Location: {p.basics.location.city}, {p.basics.location.country}. Experience ≈ {p.total_experience_years()} yrs",
        "Education: " + "; ".join(f"{e.degree} {e.field}, {e.institution} ({e.end}{', expected' if e.expected else ''})"
                                  for e in p.education[:2]),
        "Work: " + "; ".join(f"{w.title} @ {w.company} ({w.start}–{w.end or 'now'}, {w.employment_type})"
                             for w in p.work[:6]),
        "Top projects: " + "; ".join(f"{pr.name} [{', '.join(pr.skills[:6])}]" for pr in p.projects[:8]),
        "Strong/proficient skills: " + ", ".join(s.name for s in p.skills
                                                 if s.level in ("strong", "proficient") and not s.stretch)[:800],
        "Target roles: " + ", ".join(p.preferences.target_roles),
        "Resume variants available: " + (", ".join(resume_labels) or "(one default resume)"),
    ]
    return "\n".join(lines)


def score_job(gateway: LLMGateway, profile_summary: str, *, title: str, company: str, locations: list[str],
              eligibility: str, description: str, ref: str = "") -> MatchVerdict:
    user = (
        f"CANDIDATE\n{profile_summary}\n\nJOB\nTitle: {title}\nCompany: {company}\nLocations: {', '.join(locations)}\n"
        f"Work-authorization assessment: {eligibility}\n\n{untrusted('job_description', description, limit=6000)}"
    )
    return gateway.structured("job.match", SYSTEM, user, MatchVerdict, ref=ref, max_tokens=700)
