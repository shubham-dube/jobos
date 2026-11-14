from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from jobos.matching.geo import countries_for, is_remote


class NormalizedJob(BaseModel):
    source: str
    source_job_id: str
    company_name: str
    board_token: str
    url: str
    apply_url: str
    ats: str
    title: str
    department: str = ""
    locations: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    remote_type: str = "unknown"
    employment_type: str = ""
    salary: dict[str, Any] | None = None
    description_text: str = ""
    posted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def title_norm(self) -> str:
        return normalize_title(self.title)

    @property
    def fingerprint(self) -> str:
        key = f"{normalize_company(self.company_name)}|{self.title_norm}|{','.join(sorted(self.countries))}"
        return hashlib.sha1(key.encode()).hexdigest()


class Source(Protocol):
    ats: str

    def fetch(self, board_token: str, company_name: str) -> list[NormalizedJob]: ...


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|section)[^>]*>", re.I)
_WS = re.compile(r"[ \t\xa0]+")
_NL = re.compile(r"\n\s*\n+")


def html_to_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    if "<" in text:
        text = _BLOCK.sub("\n", text)
        text = _TAG.sub("", text)
        text = html.unescape(text)
    text = _WS.sub(" ", text)
    return _NL.sub("\n\n", text).strip()


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[\(\[].*?[\)\]]", " ", t)
    t = re.sub(r"[^a-z0-9+#/ ]", " ", t)
    return " ".join(t.split())


def normalize_company(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\b(inc|llc|ltd|limited|gmbh|corp|corporation|pvt|private|co)\b\.?", "", n)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", n).split())


def derive_location_fields(locations: list[str], remote_flag: bool | None = None,
                           workplace: str = "") -> tuple[list[str], str]:
    countries: set[str] = set()
    for loc in locations:
        countries |= countries_for(loc)
    wp = workplace.lower()
    if "remote" in wp or remote_flag or any(is_remote(loc) for loc in locations):
        remote_type = "remote"
    elif "hybrid" in wp or any("hybrid" in loc.lower() for loc in locations):
        remote_type = "hybrid"
    elif "onsite" in wp or "on-site" in wp or "in office" in wp:
        remote_type = "onsite"
    else:
        remote_type = "unknown" if not locations else "onsite"
    return sorted(countries), remote_type


def parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        from datetime import UTC

        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
