"""Deterministic mapping of common application fields to master-profile values.

Only unambiguous identity/contact/link fields are handled here; anything that needs judgment goes to
the LLM resolver with the full context.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from jobos_common.forms import FieldType, FillValue, FormField, FormPage, ValueSource
from jobos_common.profile import MasterProfile

COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "GB": "United Kingdom", "CH": "Switzerland", "AU": "Australia",
    "NZ": "New Zealand", "CA": "Canada", "DE": "Germany", "IE": "Ireland", "NL": "Netherlands", "SG": "Singapore",
    "AE": "United Arab Emirates", "FR": "France", "ES": "Spain", "SE": "Sweden", "JP": "Japan",
}


@dataclass
class Ctx:
    profile: MasterProfile
    job_title: str = ""
    company: str = ""
    job_countries: list[str] | None = None
    resume_document_id: str = ""
    separate_phone_country: bool = False
    documents: dict[str, str] | None = None  # kind (transcript, cover_letter, ...) -> default document id


Getter = Callable[[Ctx, FormField], tuple[object, str] | None]


def _p(ctx: Ctx) -> MasterProfile:
    return ctx.profile


def _current_work(ctx: Ctx):
    work = [w for w in ctx.profile.work if w.current] or ctx.profile.work
    work = sorted(work, key=lambda w: (-(w.priority or 0), w.start), reverse=False)
    return work[0] if work else None


def _phone(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    ph = _p(ctx).basics.phone
    if not ph.number:
        return None
    digits = re.sub(r"\D", "", ph.number)
    if ctx.separate_phone_country:
        return digits, "basics.phone.number"
    return f"{ph.country_code} {digits}".strip(), "basics.phone"


def _location_text(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    loc = _p(ctx).basics.location
    parts = [loc.city, loc.region, COUNTRY_NAMES.get(loc.country, loc.country)]
    text = ", ".join(p for p in parts if p)
    return (text, "basics.location") if text else None


def _country(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    c = _p(ctx).basics.location.country
    return (COUNTRY_NAMES.get(c, c), "basics.location.country") if c else None


def _link(attr: str) -> Getter:
    def g(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
        v = getattr(_p(ctx).basics.links, attr)
        return (v, f"basics.links.{attr}") if v else None

    return g


def _basic(attr: str) -> Getter:
    def g(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
        v = getattr(_p(ctx).basics, attr)
        if attr == "preferred_name" and not v:
            v = _p(ctx).basics.first_name
        return (v, f"basics.{attr}") if v else None

    return g


def _full_name(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    b = _p(ctx).basics
    return (f"{b.first_name} {b.last_name}".strip(), "basics.full_name") if b.first_name else None


def _legal_name(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    b = _p(ctx).basics
    return (b.full_name, "basics.legal_name") if b.first_name else None


def _preferred_first(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    b = _p(ctx).basics
    first = (b.preferred_name or b.first_name).split()[0] if (b.preferred_name or b.first_name) else ""
    return (first, "basics.preferred_name") if first else None


def _company(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    w = _current_work(ctx)
    return (w.company, f"work.{w.id}") if w else None


def _title(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    w = _current_work(ctx)
    return (w.title, f"work.{w.id}") if w else None


def _school(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    e = _p(ctx).education[0] if _p(ctx).education else None
    return (e.institution, f"education.{e.id}") if e else None


def _degree(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    e = _p(ctx).education[0] if _p(ctx).education else None
    return (e.degree, f"education.{e.id}") if e and e.degree else None


def _discipline(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    e = _p(ctx).education[0] if _p(ctx).education else None
    return (e.field, f"education.{e.id}") if e and e.field else None


def _grad_year(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    e = _p(ctx).education[0] if _p(ctx).education else None
    return (e.end[:4], f"education.{e.id}") if e and e.end else None


def _resume(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
    return (ctx.resume_document_id, "document:resume") if ctx.resume_document_id else None


def _doc(kind: str) -> Getter:
    def get(ctx: Ctx, f: FormField) -> tuple[object, str] | None:
        doc_id = (ctx.documents or {}).get(kind)
        return (doc_id, f"document:{kind}") if doc_id else None
    return get


# (label regex, allowed field types or None, getter). First match wins; order matters.
RULES: list[tuple[re.Pattern[str], set[FieldType] | None, Getter]] = [
    (re.compile(r"^(legal )?first name|^given name|^first$", re.I), None, _basic("first_name")),
    (re.compile(r"^(legal )?last name|^surname|^family name|^last$", re.I), None, _basic("last_name")),
    (re.compile(r"^legal (first and last |full )?name|^full legal name|^name \(as (on|in) (your )?(passport|id)\)", re.I),
     {FieldType.text}, _legal_name),
    (re.compile(r"^preferred first name", re.I), None, _preferred_first),
    (re.compile(r"^preferred last name", re.I), None, _basic("last_name")),
    (re.compile(r"^preferred (full )?name", re.I), None, _basic("preferred_name")),
    (re.compile(r"^(full )?name$|^full name|^your name", re.I), None, _full_name),
    (re.compile(r"e-?mail", re.I), {FieldType.email, FieldType.text}, _basic("email")),
    (re.compile(r"phone|mobile|contact number", re.I), {FieldType.phone, FieldType.text, FieldType.number}, _phone),
    (re.compile(r"linkedin", re.I), {FieldType.text, FieldType.url}, _link("linkedin")),
    (re.compile(r"github", re.I), {FieldType.text, FieldType.url}, _link("github")),
    (re.compile(r"twitter|\bx\b profile", re.I), {FieldType.text, FieldType.url}, _link("twitter")),
    (re.compile(r"portfolio|personal (web)?site|^website|blog", re.I), {FieldType.text, FieldType.url}, _link("portfolio")),
    (re.compile(r"^(current )?location|^city|where are you (currently )?(located|based)\??$", re.I),
     {FieldType.text, FieldType.combobox}, _location_text),
    (re.compile(r"^country( of residence)?$|^country$", re.I), {FieldType.select, FieldType.combobox, FieldType.text}, _country),
    (re.compile(r"(current|most recent) (company|employer)|^company$|^organi[sz]ation$|^current company", re.I),
     {FieldType.text}, _company),
    (re.compile(r"(current|most recent) (job )?title|^title$", re.I), {FieldType.text}, _title),
    (re.compile(r"^(school|university|college|institution)( name)?$", re.I), {FieldType.text, FieldType.combobox, FieldType.select}, _school),
    (re.compile(r"^degree$", re.I), {FieldType.text, FieldType.select, FieldType.combobox}, _degree),
    (re.compile(r"^(discipline|major|field of study)$", re.I), {FieldType.text, FieldType.select, FieldType.combobox}, _discipline),
    (re.compile(r"graduation (year|date)", re.I), {FieldType.text, FieldType.number}, _grad_year),
    (re.compile(r"resume|cv\b|curriculum", re.I), {FieldType.file}, _resume),
    (re.compile(r"transcript|grade ?(card|sheet|report)|mark ?sheet|academic record", re.I), {FieldType.file},
     _doc("transcript")),
    (re.compile(r"cover ?letter|motivation(al)? letter", re.I), {FieldType.file}, _doc("cover_letter")),
]

_DECLINE = re.compile(r"(decline|prefer not|don.?t wish|do not wish|not to (say|answer|disclose)|rather not)", re.I)
EEO = re.compile(r"\b(gender|race|ethnic\w*|veteran|disabilit\w*|sexual orientation|transgender|pronouns?|hispanic|latin\w*)\b", re.I)
CONSENT = re.compile(r"(i (acknowledge|agree|consent|confirm|certify|have read|have reviewed)|privacy (policy|notice)|"
                     r"terms (and|&) conditions|by (submitting|checking))", re.I)


def map_field(ctx: Ctx, f: FormField) -> FillValue | None:
    label = f.label.strip()
    for pattern, types, getter in RULES:
        if pattern.search(label) and (types is None or f.type in types):
            got = getter(ctx, f)
            if got is None:
                return None
            value, ref = got
            if f.type == FieldType.file:
                return FillValue(key=f.key, value=None, file_ref=str(value), source=ValueSource.document,
                                 source_ref=ref, confidence=1.0)
            if f.options:
                from difflib import get_close_matches

                exact = [o for o in f.options if o.lower() == str(value).lower()]
                starts = [o for o in f.options if o.lower().startswith(str(value).lower())]
                choice = (exact or starts or get_close_matches(str(value), f.options, n=1, cutoff=0.8) or [None])[0]
                if choice is None and f.locator.get("truncated"):
                    choice = str(value)  # long searchable list: the runner types it to search
                if choice is None:
                    return None
                value = choice
            return FillValue(key=f.key, value=value, source=ValueSource.profile, source_ref=ref, confidence=0.99)
    # "How did you hear about us?" - JobOS finds jobs on employers' own career sites / job boards
    if re.search(r"(how|where) did you (first )?(hear|learn|find)|source of (application|referral)|referral source",
                 label, re.I) and f.options:
        for pat in (r"company.*(web)?site|careers? (page|site|website)|career site", r"job board|job site|online job",
                    r"internet|online|web search|google", r"^other"):
            hit = [o for o in f.options if re.search(pat, o, re.I)]
            if hit:
                return FillValue(key=f.key, value=hit[0], source=ValueSource.preset, source_ref="hear_about",
                                 confidence=0.95)
    # Voluntary self-identification: decline unless the candidate set a value
    if EEO.search(label) and f.options:
        decl = [o for o in f.options if _DECLINE.search(o)]
        if decl:
            return FillValue(key=f.key, value=decl[0], source=ValueSource.preset, source_ref="demographics.decline",
                             confidence=0.98)
    # Single-option acknowledgements ("Acknowledge/Confirm") and consent checkboxes
    single_ack = len(f.options) == 1 and re.search(r"acknowledg|confirm|agree|i have (read|reviewed)|accept",
                                                    f.options[0], re.I)
    if CONSENT.search(label) or single_ack:
        if f.type == FieldType.checkbox:
            return FillValue(key=f.key, value=True, source=ValueSource.preset, source_ref="consent", confidence=0.95)
        if len(f.options) == 1 and (single_ack or CONSENT.search(label)):
            return FillValue(key=f.key, value=f.options[0], source=ValueSource.preset, source_ref="consent",
                             confidence=0.95)
    return None


def prepare_ctx(ctx: Ctx, page: FormPage) -> Ctx:
    ctx.separate_phone_country = any(
        f.options and re.search(r"country", f.label, re.I) and any(re.search(r"\+\d", o) for o in f.options[:20])
        for f in page.fields
    )
    return ctx
