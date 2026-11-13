"""Deterministic pre-filters, eligibility (work authorization / visa) and legitimacy scoring.

These run on every discovered job before any LLM call, so thousands of jobs stay cheap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from jobos_common.profile import MasterProfile

from jobos.domain.settings import SearchFilters

SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "staff"]

_SENIORITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("intern", re.compile(r"\b(intern|internship|apprentice|co-?op|trainee)\b", re.I)),
    ("staff", re.compile(r"\b(staff|principal|distinguished|director|head of|vp|vice president|chief|architect)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?|lead|manager|iii|iv|v|3|4|5|l5|l6|l7)\b", re.I)),
    ("mid", re.compile(r"\b(ii|2|l4)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|entry|graduate|new grad|associate|early career|university|i|1|l3)\b", re.I)),
]


def title_seniority(title: str) -> str:
    for level, pat in _SENIORITY_PATTERNS:
        if pat.search(title):
            return level
    return "mid"


_SPONSOR_YES = re.compile(
    r"(visa sponsorship (is )?(available|provided|offered)|we (will|can|do) sponsor|sponsorship (is )?available|"
    r"relocation (support|assistance|package)|sponsor (work )?visas?|support (your |with )?(work )?visa|"
    r"visa support|relocate you)", re.I)
_SPONSOR_NO = re.compile(
    r"((unable|not able|cannot|can't|do not|don't|does not|will not|won't|not)( be able)?( to)? "
    r"(provide |offer |support )?(visa |employment |immigration )?sponsor|no (visa )?sponsorship|"
    r"without (the need for )?(current or future )?(visa |employer )?sponsorship|"
    r"must (already )?(have|hold|possess) (the |a |valid )?(right|authori[sz]ation|eligibility) to work|"
    r"(permanent|unrestricted) (right|authori[sz]ation) to work|"
    r"(us|u\.s\.) (citizens?|persons?) only|security clearance (is )?required|must be a (us|u\.s\.) citizen)", re.I)
_REMOTE_RESTRICT = re.compile(
    r"remote[^.\n]{0,40}?\b(only|must|based)\b[^.\n]{0,60}|"
    r"(must|need to) (be )?(based|located|reside|living) in ([A-Z][\w .,&-]{2,60})", re.I)


@dataclass
class Eligibility:
    eligible: bool
    status: str  # home_country | sponsorship_offered | sponsorship_unknown | no_sponsorship | remote_ok | remote_restricted
    reasons: list[str] = field(default_factory=list)


def assess_eligibility(profile: MasterProfile, countries: list[str], remote_type: str, description: str,
                       locations: list[str]) -> Eligibility:
    home = {wa.country.upper() for wa in profile.work_authorization if not wa.needs_sponsorship and wa.country != "*"}
    if not home and profile.basics.location.country:
        home = {profile.basics.location.country.upper()}
    job_countries = {c.upper() for c in countries}
    desc = description[:20000]

    if job_countries & home:
        return Eligibility(True, "home_country", [f"Located in {', '.join(sorted(job_countries & home))}"])

    if remote_type == "remote":
        loc_text = " ".join(locations).lower()
        restricted = bool(job_countries) and not (job_countries & home)
        if not job_countries and ("anywhere" in loc_text or "global" in loc_text or "worldwide" in loc_text):
            return Eligibility(True, "remote_ok", ["Remote, location-independent"])
        if restricted or _REMOTE_RESTRICT.search(desc):
            if _SPONSOR_YES.search(desc):
                return Eligibility(True, "sponsorship_offered", ["Remote role tied to a country, sponsorship mentioned"])
            where = ", ".join(sorted(job_countries)) or "specific region"
            return Eligibility(False, "remote_restricted", [f"Remote limited to {where}"])
        return Eligibility(True, "remote_ok", ["Remote, no country restriction found"])

    # On-site/hybrid abroad
    if _SPONSOR_NO.search(desc):
        m = _SPONSOR_NO.search(desc)
        return Eligibility(False, "no_sponsorship", [f"Posting says: “{m.group(0)[:80]}”" if m else "No sponsorship"])
    if _SPONSOR_YES.search(desc):
        return Eligibility(True, "sponsorship_offered", ["Visa sponsorship / relocation support mentioned"])
    return Eligibility(True, "sponsorship_unknown", ["Abroad; sponsorship not mentioned"])


@dataclass
class FilterResult:
    passed: bool
    reasons: list[str]
    seniority: str


def apply_filters(f: SearchFilters, *, title: str, company: str, countries: list[str], remote_type: str,
                  posted_at: datetime | None, eligibility: Eligibility) -> FilterResult:
    reasons: list[str] = []
    t = title.lower()
    if f.keywords_any and not any(k.lower() in t for k in f.keywords_any):
        reasons.append("title does not match target keywords")
    for k in f.keywords_none:
        if k.lower() in t:
            reasons.append(f"title contains excluded word '{k}'")
            break
    if company.lower() in {c.lower() for c in f.exclude_companies}:
        reasons.append("company excluded")
    sen = title_seniority(title)
    if SENIORITY_ORDER.index(sen) > SENIORITY_ORDER.index(f.seniority_max):
        reasons.append(f"seniority '{sen}' above max '{f.seniority_max}'")
    if f.remote_only and remote_type != "remote":
        reasons.append("not remote")
    if f.countries:
        wanted = {c.upper() for c in f.countries}
        in_country = bool(wanted & {c.upper() for c in countries})
        if not in_country and not (f.include_remote and remote_type == "remote"):
            reasons.append("location not in target countries")
    if posted_at and f.posted_within_days:
        age = (datetime.now(UTC) - posted_at).days
        if age > f.posted_within_days:
            reasons.append(f"posted {age} days ago")
    if not eligibility.eligible and f.require_visa_friendly_abroad:
        reasons.append("not eligible: " + "; ".join(eligibility.reasons))
    return FilterResult(not reasons, reasons, sen)


def legitimacy(*, source: str, ats: str, posted_at: datetime | None, description: str,
               reposts: int = 0) -> tuple[int, list[str]]:
    """Evidence-based legitimacy score (FR-VER-1). Jobs fetched from an employer's own ATS start high."""
    score, reasons = 50, []
    if ats in {"greenhouse", "lever", "ashby", "workday", "smartrecruiters"} and source == ats:
        score += 35
        reasons.append("Listed on the employer's own applicant tracking system")
    if posted_at:
        age = (datetime.now(UTC) - posted_at).days
        if age <= 14:
            score += 10
            reasons.append(f"Fresh posting ({age}d)")
        elif age > 120:
            score -= 25
            reasons.append(f"Open for {age} days (possible ghost job)")
        elif age > 60:
            score -= 10
            reasons.append(f"Open for {age} days")
    if reposts >= 2:
        score -= 15
        reasons.append(f"Reposted {reposts} times")
    scam = re.search(r"(registration fee|training fee|pay (a|the) (fee|deposit)|telegram|whatsapp only|"
                     r"send (your )?(bank|aadhaar|ssn))", description, re.I)
    if scam:
        score -= 50
        reasons.append(f"Scam signal: “{scam.group(0)}”")
    if len(description) < 200:
        score -= 10
        reasons.append("Very short description")
    return max(0, min(100, score)), reasons


_PRIORITY_STATUS = {"home_country": 3, "remote_ok": 3, "sponsorship_offered": 2, "sponsorship_unknown": 1}


def prescore(title: str, target_roles: list[str], eligibility_status: str, legit: int) -> float:
    """Cheap ordering so the LLM budget is spent on the most promising jobs first."""
    from rapidfuzz import fuzz

    t = title.lower()
    role = max((fuzz.token_set_ratio(t, r.lower()) for r in target_roles), default=50) / 100
    return role * 3 + _PRIORITY_STATUS.get(eligibility_status, 0) + legit / 100
