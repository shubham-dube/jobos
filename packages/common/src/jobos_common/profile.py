"""Master profile: the single source of truth about the candidate.

Every fact that can end up in an application has a stable ``id`` so generated text and
fill plans can cite exactly where a value came from (ADR-0008: never fabricate).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SkillLevel(StrEnum):
    heard_of = "heard_of"
    read_about = "read_about"
    dabbled = "dabbled"
    working = "working_knowledge"
    proficient = "proficient"
    strong = "strong"


class Phone(BaseModel):
    country_code: str = ""  # e.g. "+91"
    number: str = ""  # national number without country code

    @property
    def e164(self) -> str:
        digits = "".join(ch for ch in self.number if ch.isdigit())
        return f"{self.country_code}{digits}" if digits else ""


class Location(BaseModel):
    city: str = ""
    region: str = ""  # state / province
    country: str = ""  # ISO-3166 alpha-2, e.g. "IN"
    postal_code: str = ""
    address_line: str = ""


class Links(BaseModel):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    twitter: str = ""
    leetcode: str = ""
    other: list[str] = Field(default_factory=list)


class Basics(BaseModel):
    first_name: str = ""
    last_name: str = ""
    middle_name: str = ""
    preferred_name: str = ""
    email: str = ""
    phone: Phone = Field(default_factory=Phone)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: str = ""
    summary: str = ""

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)


class Highlight(BaseModel):
    id: str
    text: str
    skills: list[str] = Field(default_factory=list)


class WorkItem(BaseModel):
    id: str
    company: str
    title: str
    start: str = ""  # YYYY-MM
    end: str | None = None  # YYYY-MM or None when current
    current: bool = False
    location: str = ""
    employment_type: str = ""  # full_time | internship | contract | founder | part_time
    remote: bool | None = None
    summary: str = ""
    highlights: list[Highlight] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    priority: int = 0  # higher = lead with it; negative = include only if space


class Education(BaseModel):
    id: str
    institution: str
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""  # as written, e.g. "7.69/10" or "94.8%"
    location: str = ""
    expected: bool = False


class Project(BaseModel):
    id: str
    name: str
    summary: str = ""
    highlights: list[Highlight] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    url: str = ""
    date: str = ""
    tier: str = ""  # S/A/B/C/H from the founder's profile


class Skill(BaseModel):
    name: str
    level: SkillLevel = SkillLevel.working
    category: str = ""
    years: float | None = None
    stretch: bool = False  # may appear for keyword matching; never claimed as strong


class Award(BaseModel):
    id: str
    title: str
    issuer: str = ""
    date: str = ""
    description: str = ""


class Language(BaseModel):
    name: str
    proficiency: str = ""


class WorkAuthorization(BaseModel):
    country: str  # ISO2, or "*" for "any other country"
    status: str = "none"  # citizen | permanent_resident | work_visa | none
    needs_sponsorship: bool = True


class Money(BaseModel):
    amount: float = 0
    currency: str = "INR"
    period: str = "year"  # year | month | hour


class Preferences(BaseModel):
    notice_period_days: int | None = None
    earliest_start_date: str = ""
    current_compensation: Money | None = None
    expected_compensation: Money | None = None
    willing_to_relocate: bool = True
    relocation_countries: list[str] = Field(default_factory=list)  # ISO2; empty = anywhere
    work_modes: list[str] = Field(default_factory=lambda: ["remote", "hybrid", "onsite"])
    target_roles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)


class Demographics(BaseModel):
    """Voluntary self-identification. Defaults to declining; never used for matching."""

    gender: str = "decline"
    pronouns: str = ""
    race_ethnicity: str = "decline"
    veteran_status: str = "decline"
    disability_status: str = "decline"
    date_of_birth: str = ""


class Fact(BaseModel):
    """Any other citable fact (exam scores, stats, availability notes...)."""

    id: str
    text: str
    tags: list[str] = Field(default_factory=list)


class MasterProfile(BaseModel):
    schema_version: int = 1
    basics: Basics = Field(default_factory=Basics)
    work: list[WorkItem] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    work_authorization: list[WorkAuthorization] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    demographics: Demographics = Field(default_factory=Demographics)
    facts: list[Fact] = Field(default_factory=list)

    # ----- helpers -----
    def fact_index(self) -> dict[str, str]:
        """id -> human readable text for every citable fact (used for grounding)."""
        idx: dict[str, str] = {}
        for w in self.work:
            idx[w.id] = f"{w.title} at {w.company} ({w.start}–{w.end or 'present'})"
            for h in w.highlights:
                idx[h.id] = h.text
        for e in self.education:
            idx[e.id] = f"{e.degree} {e.field} at {e.institution} ({e.start}–{e.end}) grade {e.grade}".strip()
        for p in self.projects:
            idx[p.id] = f"Project {p.name}: {p.summary}"
            for h in p.highlights:
                idx[h.id] = h.text
        for a in self.awards:
            idx[a.id] = f"{a.title} {a.issuer} {a.date}".strip()
        for f in self.facts:
            idx[f.id] = f.text
        return idx

    def authorization_for(self, country: str) -> WorkAuthorization:
        country = country.upper()
        for wa in self.work_authorization:
            if wa.country.upper() == country:
                return wa
        for wa in self.work_authorization:
            if wa.country == "*":
                return wa
        return WorkAuthorization(country=country, status="none", needs_sponsorship=True)

    def total_experience_years(self, kinds: tuple[str, ...] = ("full_time", "internship", "part_time", "contract")) -> float:
        """Years of paid professional experience; overlapping roles are merged, founder/volunteer roles excluded."""
        from datetime import date

        today = date.today()
        now = today.year * 12 + today.month
        spans = []
        for w in self.work:
            if w.employment_type and w.employment_type not in kinds:
                continue
            s = _ym(w.start)
            if s is None:
                continue
            e = _ym(w.end) if w.end else now
            spans.append((s, max(s, e or now)))
        months, cur_s, cur_e = 0, None, None
        for s, e in sorted(spans):
            if cur_e is None or s > cur_e:
                if cur_e is not None:
                    months += cur_e - cur_s
                cur_s, cur_e = s, e
            else:
                cur_e = max(cur_e, e)
        if cur_e is not None:
            months += cur_e - cur_s
        return round(months / 12, 1)

    def is_student(self) -> bool:
        return any(e.expected for e in self.education)


def _ym(value: str | None) -> int | None:
    if not value:
        return None
    try:
        y, m = value.split("-")[:2]
        return int(y) * 12 + int(m)
    except (ValueError, IndexError):
        try:
            return int(value[:4]) * 12 + 1
        except ValueError:
            return None
