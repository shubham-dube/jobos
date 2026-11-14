"""One-off application forms (Google Forms and other single pages) imported from a pasted or emailed link.

Unlike ATS boards there is nothing to crawl: the form itself is the posting. Its title and description become
the job text so matching, legitimacy and tailoring work as for any other job.
"""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .base import html_to_text

GFORM = re.compile(r"https://docs\.google\.com/forms/(?:u/\d+/)?d/(?:e/)?([\w-]{10,})/(?:viewform|formResponse)")


@dataclass
class FormPosting:
    ats: str
    form_id: str
    url: str
    title: str
    description: str


def is_single_form(url: str) -> bool:
    return bool(GFORM.match(url) or re.match(r"https://forms\.gle/\w+", url))


def _meta(page: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)="{prop}"[^>]+content="([^"]*)"', page, re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_form_page(url: str, page: str) -> FormPosting:
    m = GFORM.match(url)
    title = _meta(page, "og:title") or html.unescape((re.search(r"<title>([^<]*)</title>", page) or [None, ""])[1])
    description = _meta(page, "og:description") or _meta(page, "description")
    return FormPosting(ats="google_forms" if m else "form", form_id=m.group(1) if m else uuid.uuid4().hex[:12],
                       url=url.split("?")[0] if m else url, title=title.strip() or "Application form",
                       description=html_to_text(description))


def fetch_form(url: str, client: httpx.Client | None = None) -> FormPosting:
    c = client or httpx.Client(timeout=20, follow_redirects=True)
    r = c.get(url)
    r.raise_for_status()
    return parse_form_page(str(r.url), r.text)


def host(url: str) -> str:
    return urlparse(url).hostname or ""
