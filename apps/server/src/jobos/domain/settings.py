"""Candidate settings: approval rules (ADR-0015), pacing, caps, search filters."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class RuleConditions(BaseModel):
    ats_in: list[str] = Field(default_factory=list)
    company_in: list[str] = Field(default_factory=list)
    company_not_in: list[str] = Field(default_factory=list)
    countries_in: list[str] = Field(default_factory=list)
    remote_only: bool = False
    min_match_score: int | None = None
    min_legitimacy: int | None = None
    max_generated_fields: int | None = None
    max_low_confidence_fields: int | None = None
    answer_sources_subset_of: list[str] = Field(default_factory=list)
    platform_native: bool | None = None


class ApprovalRule(BaseModel):
    name: str
    enabled: bool = True
    when: RuleConditions = Field(default_factory=RuleConditions)
    action: str = "review"  # auto_submit | review


class GateFacts(BaseModel):
    """Everything the approval rules can look at for one application."""

    ats: str
    company: str
    countries: list[str] = Field(default_factory=list)
    remote: bool = False
    match_score: int | None = None
    legitimacy: int | None = None
    generated_fields: int = 0
    low_confidence_fields: int = 0
    answer_sources: list[str] = Field(default_factory=list)
    platform_native: bool = False


def _matches(cond: RuleConditions, f: GateFacts) -> bool:
    def low(xs: list[str]) -> set[str]:
        return {x.lower() for x in xs}

    if cond.ats_in and f.ats.lower() not in low(cond.ats_in):
        return False
    if cond.company_in and f.company.lower() not in low(cond.company_in):
        return False
    if cond.company_not_in and f.company.lower() in low(cond.company_not_in):
        return False
    if cond.countries_in and not (low(f.countries) & low(cond.countries_in)):
        return False
    if cond.remote_only and not f.remote:
        return False
    if cond.min_match_score is not None and (f.match_score or 0) < cond.min_match_score:
        return False
    if cond.min_legitimacy is not None and (f.legitimacy or 0) < cond.min_legitimacy:
        return False
    if cond.max_generated_fields is not None and f.generated_fields > cond.max_generated_fields:
        return False
    if cond.max_low_confidence_fields is not None and f.low_confidence_fields > cond.max_low_confidence_fields:
        return False
    if cond.answer_sources_subset_of and not set(f.answer_sources) <= set(cond.answer_sources_subset_of):
        return False
    return not (cond.platform_native is not None and cond.platform_native != f.platform_native)


def decide(rules: list[ApprovalRule], facts: GateFacts) -> tuple[str, str]:
    """Return (action, rule_name). Default is review (ADR-0015)."""
    for rule in rules:
        if rule.enabled and _matches(rule.when, facts):
            return rule.action, rule.name
    return "review", "default"


class ActiveHours(BaseModel):
    start: time = time(8, 0)
    end: time = time(23, 0)
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # Mon=0

    def contains(self, now: datetime, tz: str) -> bool:
        local = now.astimezone(ZoneInfo(tz))
        if local.weekday() not in self.days:
            return False
        t = local.time()
        if self.start <= self.end:
            return self.start <= t <= self.end
        return t >= self.start or t <= self.end


class Pacing(BaseModel):
    daily_cap: int = 150  # max submissions per day (all sites)
    per_company_daily_cap: int = 2
    min_gap_seconds: int = 60  # min gap between two submissions on the same runner
    max_gap_seconds: int = 240
    active_hours: ActiveHours = Field(default_factory=ActiveHours)
    reapply_cooldown_days: int = 60  # same company + similar title


class Thresholds(BaseModel):
    min_match_score_to_queue: int = 60
    min_legitimacy_to_queue: int = 50
    auto_answer_confidence: float = 0.8  # answer-bank reuse threshold


class CandidateSettings(BaseModel):
    approval_rules: list[ApprovalRule] = Field(default_factory=list)  # empty => review everything
    pacing: Pacing = Field(default_factory=Pacing)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    platform_native_enabled: list[str] = Field(default_factory=list)  # e.g. ["linkedin", "naukri"]
    notify_channels: list[str] = Field(default_factory=lambda: ["email", "whatsapp"])


class SearchFilters(BaseModel):
    """A saved search (search_profiles.filters)."""

    keywords_any: list[str] = Field(default_factory=list)  # title must contain one of these
    keywords_none: list[str] = Field(default_factory=list)  # title must contain none
    countries: list[str] = Field(default_factory=list)  # ISO2; empty = anywhere
    include_remote: bool = True
    remote_only: bool = False
    exclude_companies: list[str] = Field(default_factory=list)
    seniority_max: str = "mid"  # intern|junior|mid|senior|staff
    require_visa_friendly_abroad: bool = True
    posted_within_days: int = 45
    sources: list[str] = Field(default_factory=lambda: ["greenhouse", "lever", "ashby"])
