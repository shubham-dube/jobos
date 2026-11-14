"""Find employers' public ATS job boards from company names (spec 0001 AC2 "grows"; ADR-0017).

We only probe the employers' own public ATS APIs (the same ones we crawl), politely and with cheap requests:
- Greenhouse: board info (returns the board's company name, so we can check it is the right company)
- Lever: postings with limit=1
- Ashby: HEAD on the posting API
Shortened slug guesses ("scale" for "Scale AI") are only accepted where the API returns a name we can verify.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib import resources

import httpx
import structlog
from rapidfuzz import fuzz

log = structlog.get_logger(__name__)

_SUFFIXES = re.compile(r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|gmbh|plc|pvt|private|technologies|"
                       r"technology|labs|hq|group|holdings)\b\.?", re.I)
USER_AGENT = "JobOS board discovery (employer ATS public APIs)"


@dataclass(frozen=True)
class Slug:
    value: str
    exact: bool  # derived from the full name (safe without a name check)


@dataclass
class Found:
    name: str
    ats: str
    board_token: str
    jobs: int


def slug_variants(name: str) -> list[Slug]:
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    words = re.findall(r"[a-z0-9]+", base)
    core = re.findall(r"[a-z0-9]+", _SUFFIXES.sub(" ", base))
    out: list[Slug] = []
    for words_, exact in ((words, True), (core, False)):
        if not words_:
            continue
        for v in ("".join(words_), "-".join(words_)):
            if v and all(s.value != v for s in out):
                out.append(Slug(v, exact and v in ("".join(words), "-".join(words))))
    if len(core) > 1 and len(core[0]) >= 4 and all(s.value != core[0] for s in out):
        out.append(Slug(core[0], False))  # "scale" for "Scale AI": only with a name check
    return out[:5]


class BoardProber:
    def __init__(self, client: httpx.Client | None = None, delay_s: float = 0.15):
        self.client = client or httpx.Client(timeout=15, follow_redirects=False,
                                             headers={"User-Agent": USER_AGENT})
        self.delay_s = delay_s

    def _get(self, url: str, head: bool = False) -> httpx.Response | None:
        time.sleep(self.delay_s)
        try:
            return self.client.head(url) if head else self.client.get(url)
        except httpx.HTTPError as exc:
            log.debug("probe.error", url=url, error=str(exc))
            return None

    def greenhouse(self, name: str, slug: Slug) -> Found | None:
        r = self._get(f"https://boards-api.greenhouse.io/v1/boards/{slug.value}")
        if r is None or r.status_code != 200:
            return None
        board_name = (r.json() or {}).get("name") or ""
        if fuzz.token_sort_ratio(_norm(board_name), _norm(name)) < 85:
            return None  # a different company owns this slug
        jobs = self._get(f"https://boards-api.greenhouse.io/v1/boards/{slug.value}/jobs")
        n = len((jobs.json() or {}).get("jobs", [])) if jobs is not None and jobs.status_code == 200 else 0
        return Found(board_name or name, "greenhouse", slug.value, n)

    def lever(self, name: str, slug: Slug) -> Found | None:
        if not slug.exact:
            return None
        r = self._get(f"https://api.lever.co/v0/postings/{slug.value}?mode=json&limit=1")
        if r is None or r.status_code != 200:
            return None
        return Found(name, "lever", slug.value, len(r.json() or []))

    def ashby(self, name: str, slug: Slug) -> Found | None:
        r = self._get(f"https://api.ashbyhq.com/posting-api/job-board/{slug.value}", head=True)
        if r is None or r.status_code != 200:
            return None
        # The API has no company name; the hosted board's <title> ("Ramp Jobs") lets us verify the owner.
        page = self._get(f"https://jobs.ashbyhq.com/{slug.value}")
        m = re.search(r"<title>([^<]*)</title>", page.text if page is not None else "", re.I)
        title = re.sub(r"\bjobs?\b|\bcareers?\b", " ", m.group(1) if m else "", flags=re.I)
        if fuzz.token_sort_ratio(_norm(title), _norm(name)) < 85:
            return None
        return Found(name, "ashby", slug.value, 1)  # the first crawl counts the jobs

    def probe(self, name: str) -> list[Found]:
        """All boards found for one company (a company can use more than one ATS over time)."""
        found: list[Found] = []
        for probe in (self.greenhouse, self.lever, self.ashby):
            for slug in slug_variants(name):
                hit = probe(name, slug)
                if hit:
                    found.append(hit)
                    break
        return [f for f in found if f.jobs > 0]


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _SUFFIXES.sub(" ", s.lower())))


def candidate_names() -> list[str]:
    text = resources.files("jobos.sources").joinpath("board_candidates.txt").read_text()
    names = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return list(dict.fromkeys(names))


def discover(names: Iterable[str], prober: BoardProber | None = None, workers: int = 4) -> list[Found]:
    p = prober or BoardProber()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(p.probe, names))
    return [f for group in results for f in group]
