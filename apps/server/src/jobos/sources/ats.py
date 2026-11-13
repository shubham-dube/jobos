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
                # The hosted board form works even when the company embeds Greenhouse on its own site.
                apply_url=f"https://job-boards.greenhouse.io/{board_token}/jobs/{jid}",
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
    ]
    for pat, ats in patterns:
        m = re.search(pat, url)
        if m:
            return ats, m.group(1)
    return None
