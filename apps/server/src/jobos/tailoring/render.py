"""Typst rendering for tailored resumes and cover letters (ADR-0018): offline, data via sys.inputs JSON."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from jobos_common.profile import MasterProfile

from .model import ResumeVariant

FONTS = ["Calibri", "Carlito", "Arial", "Liberation Sans", "Inter", "DejaVu Sans", "Libertinus Serif"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_SCHOOL = ("school", "secondary", "12th", "10th", "class x", "hsc", "ssc", "cbse", "matric")
LETTER_COUNTRIES = {"US", "CA", "MX", "PH"}


def paper_for(countries: list[str] | None) -> str:
    return "us-letter" if countries and countries[0].upper() in LETTER_COUNTRIES else "a4"


def _month(ym: str | None) -> str:
    if not ym:
        return ""
    parts = ym.split("-")
    if len(parts) >= 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12:
        return f"{_MONTHS[int(parts[1]) - 1]} {parts[0]}"
    return parts[0]


def _span(start: str, end: str | None, current: bool = False) -> str:
    a, b = _month(start), ("Present" if current or not end else _month(end))
    return f"{a} – {b}" if a else b


def _strip_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _compile(template: str, data: dict[str, Any]) -> bytes:
    import typst

    tpl = resources.files("jobos.tailoring").joinpath("templates", template)
    with resources.as_file(tpl) as path:
        return typst.compile(str(Path(path)), sys_inputs={"data": json.dumps(data, ensure_ascii=False)})


def page_count(pdf: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(pdf)).pages)


def pdf_text(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


def _header(p: MasterProfile) -> tuple[list[str], list[dict[str, str]]]:
    from jobos.forms.taxonomy import COUNTRY_NAMES

    b = p.basics
    loc = ", ".join(x for x in [b.location.city, COUNTRY_NAMES.get(b.location.country.upper(), b.location.country)] if x)
    phone = f"{b.phone.country_code} {b.phone.number}".strip()
    contact = [x for x in [b.email, phone, loc] if x]
    links = [{"label": _strip_url(u), "url": u} for u in [b.links.linkedin, b.links.github, b.links.portfolio] if u]
    return contact, links


def resume_data(p: MasterProfile, v: ResumeVariant, *, paper: str = "a4", size: float = 10.0) -> dict[str, Any]:
    contact, links = _header(p)
    work = {w.id: w for w in p.work}
    projects = {pr.id: pr for pr in p.projects}
    awards = {a.id: a for a in p.awards}

    edu = [e for i, e in enumerate(p.education)
           if i == 0 or not any(k in f"{e.institution} {e.degree}".lower() for k in _SCHOOL)]
    education = [{
        "title": e.institution, "org": "",
        "right": (("Expected " if e.expected else "") + _month(e.end)) if e.end else "",
        "sub": " · ".join(x for x in [f"{e.degree} in {e.field}" if e.field else e.degree, e.grade] if x),
        "location": e.location, "bullets": [],
    } for e in edu]
    experience = [{
        "title": work[it.id].title, "org": work[it.id].company,
        "right": _span(work[it.id].start, work[it.id].end, work[it.id].current),
        "sub": "", "location": work[it.id].location, "bullets": [b.text for b in it.bullets],
    } for it in v.experience if it.id in work]
    projs = [{
        "title": projects[it.id].name, "org": "", "right": _month(projects[it.id].date),
        "sub": ", ".join(projects[it.id].skills[:6]), "location": _strip_url(projects[it.id].url),
        "bullets": [b.text for b in it.bullets],
    } for it in v.projects if it.id in projects]

    cats: dict[str, list[str]] = {}
    category = {s.name: s.category for s in p.skills}
    for name in v.skills:
        cats.setdefault(category.get(name, ""), []).append(name)
    skills = [{"label": k, "items": vals} for k, vals in cats.items()]

    student = p.is_student()
    order = (["summary", "education", "experience", "projects", "skills", "awards"] if student
             else ["summary", "experience", "projects", "education", "skills", "awards"])
    return {
        "page": paper, "fonts": FONTS, "size": size, "name": p.basics.full_name, "contact": contact, "links": links,
        "summary": v.summary.text if v.summary else None, "order": order, "education": education,
        "experience": experience, "projects": projs, "skills": skills,
        "awards": [" ".join(x for x in [awards[a].title, f"({awards[a].issuer})" if awards[a].issuer else "",
                                        awards[a].date] if x) for a in v.awards if a in awards],
    }


@dataclass
class Rendered:
    pdf: bytes
    pages: int
    variant: ResumeVariant
    trimmed: list[str]


def _trims(v: ResumeVariant) -> list[tuple[str, Any]]:
    """Ordered, least-valuable-first edits that shorten the page."""
    steps: list[tuple[str, Any]] = []
    if len(v.awards) > 1:
        steps.append(("drop last award", lambda x: x.awards.pop()))
    for it in reversed(v.projects):
        if len(it.bullets) > 1:
            steps.append((f"shorten project {it.id}", lambda x, i=it.id: next(p for p in x.projects if p.id == i).bullets.pop()))
    if len(v.projects) > 1:
        steps.append(("drop last project", lambda x: x.projects.pop()))
    if len(v.skills) > 12:
        steps.append(("fewer skills", lambda x: x.__setattr__("skills", x.skills[:12])))
    for it in reversed(v.experience):
        if len(it.bullets) > 2:
            steps.append((f"shorten role {it.id}", lambda x, i=it.id: next(e for e in x.experience if e.id == i).bullets.pop()))
    if v.summary is not None:
        steps.append(("drop summary", lambda x: x.__setattr__("summary", None)))
    return steps


def render_resume(p: MasterProfile, variant: ResumeVariant, *, paper: str = "a4", max_pages: int = 1) -> Rendered:
    v = variant.model_copy(deep=True)
    trimmed: list[str] = []
    size = 10.0
    for _ in range(40):
        pdf = _compile("resume.typ", resume_data(p, v, paper=paper, size=size))
        pages = page_count(pdf)
        if pages <= max_pages:
            return Rendered(pdf, pages, v, trimmed)
        steps = _trims(v)
        if steps:
            name, fn = steps[0]
            fn(v)
            trimmed.append(name)
        elif size > 9.0:
            size -= 0.5
            trimmed.append(f"font {size}pt")
        else:
            break
    return Rendered(pdf, pages, v, trimmed)


def render_cover_letter(p: MasterProfile, paragraphs: list[str], *, company: str, greeting: str, closing: str,
                        paper: str = "a4") -> bytes:
    contact, links = _header(p)
    return _compile("cover_letter.typ", {
        "page": paper, "fonts": FONTS, "name": p.basics.full_name, "contact": contact + [lk["label"] for lk in links],
        "date": date.today().strftime("%d %B %Y"), "recipient": f"Hiring Team\n{company}".replace("\n", ", "),
        "greeting": greeting, "paragraphs": paragraphs, "closing": closing,
    })
