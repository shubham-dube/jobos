"""Learned site recipes (ADR-0014): declarative site knowledge captured from successful runs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobos.db.models import SiteRecipe
from jobos_common.forms import FillPlan, FormPage, ValueSource

# values that may be reused on other jobs of the same site
_REUSABLE = {ValueSource.answer_bank, ValueSource.user, ValueSource.preset, ValueSource.recipe}
_KNOWN_PLATFORMS = {"greenhouse", "lever", "ashby", "workday", "smartrecruiters", "icims", "workable"}


def site_key_for(ats: str, url: str, board_token: str = "") -> str:
    if ats in _KNOWN_PLATFORMS and board_token:
        return f"{ats}:{board_token.lower()}"
    host = (urlparse(url).hostname or "").lower()
    return f"{ats}:{host}" if ats != "unknown" else f"site:{host}"


def get_recipe(s: Session, site_key: str) -> SiteRecipe | None:
    return s.scalar(select(SiteRecipe).where(SiteRecipe.site_key == site_key))


def recipe_fields(s: Session, site_key: str) -> dict[str, Any]:
    r = get_recipe(s, site_key)
    if r is None or r.status == "demoted":
        return {}
    return dict((r.data or {}).get("fields", {}))


def recipe_nav(s: Session, site_key: str) -> list[str]:
    r = get_recipe(s, site_key)
    if r is None or r.status == "demoted":
        return []
    return list((r.data or {}).get("nav", []))


def note_job_seen(s: Session, site_key: str, ats: str) -> SiteRecipe:
    r = get_recipe(s, site_key)
    if r is None:
        r = SiteRecipe(site_key=site_key, ats=ats, data={"fields": {}, "nav": []}, jobs_seen=0)
        s.add(r)
    r.jobs_seen += 1
    # recurring site (ADR-0014): second distinct job or a known ATS platform
    if r.status == "learning" and (r.jobs_seen >= 2 or ats in _KNOWN_PLATFORMS):
        r.status = "active"
    s.flush()
    return r


def learn_from_success(s: Session, site_key: str, pages: list[FormPage], plans: list[FillPlan],
                       nav_labels: list[str] | None = None) -> None:
    r = get_recipe(s, site_key)
    if r is None:
        return
    data = dict(r.data or {})
    fields = dict(data.get("fields", {}))
    by_page = {p.page_index: p for p in pages}
    for plan in plans:
        page = by_page.get(plan.page_index)
        if page is None:
            continue
        for v in plan.values:
            f = page.field(v.key)
            if f is None or v.source not in _REUSABLE or v.value is None:
                continue
            fields[f.signature] = {"label": f.label, "value": v.value, "source": v.source.value}
    data["fields"] = fields
    if nav_labels:
        data["nav"] = nav_labels
    r.data = data
    r.successes += 1


def note_failure(s: Session, site_key: str) -> None:
    r = get_recipe(s, site_key)
    if r is None:
        return
    r.failures += 1
    if r.failures >= 2 and r.failures > r.successes:
        r.status = "demoted"
