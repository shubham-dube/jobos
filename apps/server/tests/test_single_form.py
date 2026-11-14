"""Google Forms links become single jobs (title/description from the form)."""

from __future__ import annotations

from jobos.services.discovery import import_single_form
from jobos.sources.single_form import is_single_form, parse_form_page

PAGE = ('<html><head><title>Backend Intern Application</title>'
        '<meta property="og:title" content="Backend Intern Application - Acme">'
        '<meta property="og:description" content="Acme is hiring backend interns (Python, FastAPI). &amp; more">'
        '</head><body></body></html>')
URL = "https://docs.google.com/forms/d/e/1FAIpQLSexampleFormId123/viewform?usp=sf_link"


def test_parse_and_import_google_form(session) -> None:
    assert is_single_form(URL) and is_single_form("https://forms.gle/abc123")
    assert not is_single_form("https://jobs.lever.co/acme/123")
    p = parse_form_page(URL, PAGE)
    assert (p.ats, p.form_id, p.url) == ("google_forms", "1FAIpQLSexampleFormId123",
                                         "https://docs.google.com/forms/d/e/1FAIpQLSexampleFormId123/viewform")
    assert p.title == "Backend Intern Application - Acme" and "& more" in p.description
    job = import_single_form(session, p, "Acme")
    again = import_single_form(session, p, "Acme")
    assert job.id == again.id and job.ats == "google_forms" and job.apply_url == p.url
    assert job.company_name == "Acme" and "FastAPI" in job.description_text
