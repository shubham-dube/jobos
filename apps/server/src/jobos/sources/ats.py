"""Public job-board API connectors: Greenhouse, Lever, Ashby (docs/research/job-sources.md)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import NormalizedJob, derive_location_fields, html_to_text, parse_dt


class SourceError(RuntimeError):
    def __init__(self, message: str, *, not_found: bool = False):
        super().__init__(message)
        self.not_found = not_found


def _get_json(client: httpx.Client, url: str) -> Any:
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = client.get(url)
        except httpx.TransportError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 404:
            raise SourceError(f"board not found: {url}", not_found=True)
        if r.status_code in (429, 500, 502, 503, 504):
            last = SourceError(f"HTTP {r.status_code} for {url}")
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise SourceError(f"failed after retries: {url}: {last}")


def default_client() -> httpx.Client:
    return httpx.Client(timeout=30, headers={"User-Agent": "JobOS/0.1 (job discovery)"}, follow_redirects=True)


class GreenhouseSource:
    ats = "greenhouse"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    def fetch(self, board_token: str, company_name: str) -> list[NormalizedJob]:
        data = _get_json(self.client, f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true")
        jobs: list[NormalizedJob] = []
        for j in data.get("jobs", []):
            loc = (j.get("location") or {}).get("name", "") or ""
            locations = [loc] if loc else []
            for o in j.get("offices") or []:
                if o.get("location"):
                    locations.append(o["location"])
            countries, remote = derive_location_fields(locations)
            depts = j.get("departments") or []
            jid = str(j["id"])
            jobs.append(NormalizedJob(
                source="greenhouse", source_job_id=f"{board_token}:{jid}", company_name=j.get("company_name") or company_name,
                board_token=board_token, url=j.get("absolute_url") or "",
                # The embed form renders directly even when the company redirects hosted pages to its own site.
                apply_url=f"https://job-boards.greenhouse.io/embed/job_app?for={board_token}&token={jid}",
                ats="greenhouse", title=j.get("title", "").strip(),
                department=depts[0]["name"] if depts else "",
                locations=locations, countries=countries, remote_type=remote,
                description_text=html_to_text(j.get("content", "")),
                posted_at=parse_dt(j.get("first_published") or j.get("updated_at")),
                raw={"id": jid, "updated_at": j.get("updated_at"), "internal_job_id": j.get("internal_job_id")},
            ))
        return jobs


class LeverSource:
    ats = "lever"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    def fetch(self, board_token: str, company_name: str) -> list[NormalizedJob]:
        data = _get_json(self.client, f"https://api.lever.co/v0/postings/{board_token}?mode=json")
        jobs: list[NormalizedJob] = []
        for j in data:
            cats = j.get("categories") or {}
            locations = list(cats.get("allLocations") or ([cats["location"]] if cats.get("location") else []))
            countries, remote = derive_location_fields(locations, workplace=j.get("workplaceType") or "")
            if j.get("country") and j["country"] not in countries:
                countries = sorted({*countries, j["country"]})
            desc = "\n\n".join(filter(None, [
                j.get("descriptionPlain") or html_to_text(j.get("description", "")),
                *[f"{li.get('text', '')}\n{html_to_text(li.get('content', ''))}" for li in j.get("lists") or []],
                j.get("additionalPlain") or "",
            ]))
            salary = None
            if j.get("salaryRange"):
                sr = j["salaryRange"]
                salary = {"min": sr.get("min"), "max": sr.get("max"), "currency": sr.get("currency"),
                          "period": sr.get("interval")}
            jobs.append(NormalizedJob(
                source="lever", source_job_id=f"{board_token}:{j['id']}", company_name=company_name,
                board_token=board_token, url=j.get("hostedUrl", ""),
                apply_url=j.get("applyUrl") or f"{j.get('hostedUrl', '')}/apply", ats="lever",
                title=(j.get("text") or "").strip(), department=cats.get("team", "") or "",
                locations=locations, countries=countries, remote_type=remote,
                employment_type=cats.get("commitment", "") or "", salary=salary,
                description_text=desc, posted_at=parse_dt(j.get("createdAt")), raw={"id": j["id"]},
            ))
        return jobs


class AshbySource:
    ats = "ashby"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    def fetch(self, board_token: str, company_name: str) -> list[NormalizedJob]:
        data = _get_json(self.client,
                         f"https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true")
        jobs: list[NormalizedJob] = []
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            locations = [j["location"]] if j.get("location") else []
            for sl in j.get("secondaryLocations") or []:
                if isinstance(sl, dict) and sl.get("location"):
                    locations.append(sl["location"])
            addr = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
            countries, remote = derive_location_fields(locations, remote_flag=j.get("isRemote"),
                                                       workplace=j.get("workplaceType") or "")
            if addr:
                from jobos.matching.geo import countries_for

                countries = sorted({*countries, *countries_for(addr)})
            comp = j.get("compensation") or {}
            salary = {"summary": comp.get("scrapeableCompensationSalarySummary")} if comp.get(
                "scrapeableCompensationSalarySummary") else None
            jobs.append(NormalizedJob(
                source="ashby", source_job_id=f"{board_token}:{j['id']}", company_name=company_name,
                board_token=board_token, url=j.get("jobUrl", ""),
                apply_url=j.get("applyUrl") or f"{j.get('jobUrl', '')}/application", ats="ashby",
                title=(j.get("title") or "").strip(), department=j.get("department", "") or "",
                locations=locations, countries=countries, remote_type=remote,
                employment_type=j.get("employmentType", "") or "", salary=salary,
                description_text=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
                posted_at=parse_dt(j.get("publishedAt")), raw={"id": j["id"]},
            ))
        return jobs


SOURCES: dict[str, type[GreenhouseSource] | type[LeverSource] | type[AshbySource]] = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "ashby": AshbySource,
}


def detect_ats_from_url(url: str) -> tuple[str, str] | None:
    """Return (ats, board_token) for a known ATS job URL, used to grow the company list."""
    import re

    patterns = [
        (r"(?:job-boards|boards)\.greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)", "greenhouse"),
        (r"jobs\.lever\.co/([\w.-]+)", "lever"),
        (r"jobs\.ashbyhq\.com/([\w.-]+)", "ashby"),
        (r"jobs\.smartrecruiters\.com/([\w.-]+)", "smartrecruiters"),
        (r"apply\.workable\.com/([\w.-]+)", "workable"),
    ]
    for pat, ats in patterns:
        m = re.search(pat, url)
        if m and m.group(1) not in ("j", "api"):
            return ats, m.group(1)
    m = re.search(r"https?://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", url)
    if m:
        return "workday", f"{m.group(1)}.{m.group(2)}.myworkdayjobs.com|{m.group(1)}|{m.group(3)}"
    return None


# ---------------------------------------------------------------------------------------------
# Sources whose list endpoints have no descriptions: jobs are stored with raw["needs_hydrate"]=True
# and `hydrate()` fetches the description only for jobs that pass the cheap pre-filters.

class SmartRecruitersSource:
    ats = "smartrecruiters"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    def fetch(self, board_token: str, company_name: str, max_jobs: int = 3000) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        offset = 0
        while offset < max_jobs:
            data = _get_json(self.client, f"https://api.smartrecruiters.com/v1/companies/{board_token}/postings"
                                          f"?limit=100&offset={offset}")
            content = data.get("content", [])
            for j in content:
                loc = j.get("location") or {}
                text = ", ".join(x for x in [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()] if x)
                countries, remote = derive_location_fields([text], remote_flag=loc.get("remote"),
                                                           workplace="hybrid" if loc.get("hybrid") else "")
                if loc.get("country"):
                    countries = sorted({*countries, loc["country"].upper()})
                jid = str(j["id"])
                slug = f"https://jobs.smartrecruiters.com/{board_token}/{jid}"
                jobs.append(NormalizedJob(
                    source="smartrecruiters", source_job_id=f"{board_token}:{jid}",
                    company_name=(j.get("company") or {}).get("name") or company_name, board_token=board_token,
                    url=slug, apply_url=slug, ats="smartrecruiters", title=(j.get("name") or "").strip(),
                    department=(j.get("function") or {}).get("label", "") or "", locations=[text] if text else [],
                    countries=countries, remote_type=remote,
                    employment_type=(j.get("typeOfEmployment") or {}).get("label", "") or "",
                    posted_at=parse_dt(j.get("releasedDate")),
                    raw={"id": jid, "needs_hydrate": True,
                         "experience": (j.get("experienceLevel") or {}).get("id", "")},
                ))
            offset += len(content)
            if not content or offset >= int(data.get("totalFound") or 0):
                break
        return jobs

    def hydrate(self, board_token: str, raw: dict) -> dict:
        d = _get_json(self.client, f"https://api.smartrecruiters.com/v1/companies/{board_token}/postings/{raw['id']}")
        sections = ((d.get("jobAd") or {}).get("sections") or {})
        text = "\n\n".join(f"{s.get('title', '')}\n{html_to_text(s.get('text', ''))}" for s in sections.values()
                           if isinstance(s, dict))
        return {"description_text": text, "apply_url": d.get("applyUrl") or d.get("postingUrl")}


class WorkableSource:
    ats = "workable"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    def fetch(self, board_token: str, company_name: str) -> list[NormalizedJob]:
        data = _get_json(self.client, f"https://apply.workable.com/api/v1/widget/accounts/{board_token}?details=true")
        name = data.get("name") or company_name
        jobs: list[NormalizedJob] = []
        for j in data.get("jobs", []):
            locs = j.get("locations") or [{"city": j.get("city"), "country": j.get("country"),
                                           "countryCode": None}]
            texts = [", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x) for loc in locs]
            countries, remote = derive_location_fields(texts, remote_flag=bool(j.get("telecommuting")))
            countries = sorted({*countries, *[loc["countryCode"] for loc in locs if loc.get("countryCode")]})
            desc = html_to_text(j.get("description") or "")
            jobs.append(NormalizedJob(
                source="workable", source_job_id=f"{board_token}:{j['shortcode']}", company_name=name,
                board_token=board_token, url=j.get("url") or j.get("shortlink", ""),
                apply_url=j.get("application_url") or f"{j.get('url', '')}/apply", ats="workable",
                title=(j.get("title") or "").strip(), department=j.get("department", "") or "",
                locations=texts, countries=countries, remote_type=remote,
                employment_type=j.get("employment_type", "") or "", description_text=desc,
                posted_at=parse_dt(j.get("published_on") or j.get("created_at")),
                raw={"shortcode": j["shortcode"], "needs_hydrate": not desc},
            ))
        return jobs

    def hydrate(self, board_token: str, raw: dict) -> dict:
        d = _get_json(self.client, f"https://apply.workable.com/api/v2/accounts/{board_token}/jobs/{raw['shortcode']}")
        parts = [d.get("description"), d.get("requirements"), d.get("benefits")]
        return {"description_text": "\n\n".join(html_to_text(p) for p in parts if p)}


class WorkdaySource:
    """Workday career sites. board_token = "<host>|<tenant>|<site>", e.g.
    "nvidia.wd5.myworkdayjobs.com|nvidia|NVIDIAExternalCareerSite"."""

    ats = "workday"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or default_client()

    @staticmethod
    def parse_token(board_token: str) -> tuple[str, str, str]:
        host, tenant, site = board_token.split("|")
        return host, tenant, site

    def fetch(self, board_token: str, company_name: str, max_jobs: int = 4000) -> list[NormalizedJob]:
        host, tenant, site = self.parse_token(board_token)
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        jobs: list[NormalizedJob] = []
        offset, total = 0, None
        while offset < max_jobs:
            last: Exception | None = None
            for attempt in range(3):
                try:
                    r = self.client.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset,
                                                               "searchText": ""})
                    if r.status_code == 404:
                        raise SourceError(f"workday site not found: {board_token}", not_found=True)
                    r.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    last = exc
                    time.sleep(2 * (attempt + 1))
            else:
                raise SourceError(f"workday list failed: {last}")
            data = r.json()
            total = data.get("total", total) if total is None else total
            postings = data.get("jobPostings", [])
            for p in postings:
                path = p.get("externalPath", "")
                loc = p.get("locationsText", "") or ""
                countries, remote = derive_location_fields([loc])
                req = (p.get("bulletFields") or [path.rsplit("_", 1)[-1]])[0]
                jobs.append(NormalizedJob(
                    source="workday", source_job_id=f"{tenant}:{req}", company_name=company_name,
                    board_token=board_token, url=f"https://{host}/{site}{path}",
                    apply_url=f"https://{host}/{site}{path}/apply", ats="workday", title=(p.get("title") or "").strip(),
                    locations=[loc] if loc else [], countries=countries, remote_type=remote,
                    posted_at=_workday_posted(p.get("postedOn", "")), raw={"path": path, "needs_hydrate": True},
                ))
            offset += len(postings)
            if not postings or (total is not None and offset >= total):
                break
            time.sleep(0.3)  # polite paging
        return jobs

    def hydrate(self, board_token: str, raw: dict) -> dict:
        host, tenant, site = self.parse_token(board_token)
        d = _get_json(self.client, f"https://{host}/wday/cxs/{tenant}/{site}{raw['path']}")
        info = d.get("jobPostingInfo") or {}
        out: dict = {"description_text": html_to_text(info.get("jobDescription", ""))}
        if info.get("startDate"):
            out["posted_at"] = parse_dt(info["startDate"] + "T00:00:00+00:00")
        country = (info.get("country") or {}).get("descriptor")
        if country:
            from jobos.matching.geo import countries_for

            out["countries"] = sorted(countries_for(country))
        if info.get("remoteType"):
            out["remote_type"] = "remote" if "remote" in str(info["remoteType"]).lower() else "hybrid"
        return out


def _workday_posted(text: str):
    """'Posted Today' / 'Posted Yesterday' / 'Posted 5 Days Ago' / 'Posted 30+ Days Ago' -> datetime."""
    import re
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    t = text.lower()
    if "today" in t:
        return now
    if "yesterday" in t:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", t)
    return now - timedelta(days=int(m.group(1))) if m else None


SOURCES.update({"smartrecruiters": SmartRecruitersSource, "workable": WorkableSource,  # type: ignore[dict-item]
                "workday": WorkdaySource})
