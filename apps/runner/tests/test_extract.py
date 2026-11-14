"""Extractor regression tests against local HTML fixtures (no network)."""

from __future__ import annotations

import asyncio
import glob
import os
from pathlib import Path

import pytest

CHROME = os.environ.get("JOBOS_TEST_CHROME") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")), "")
FIX = Path(__file__).parents[2] / "server/tests/fixtures/fake_ats"


@pytest.mark.skipif(not CHROME, reason="no Chromium")
def test_fieldset_checkboxes_group_into_multiselect() -> None:
    from playwright.async_api import async_playwright

    from jobos_runner.human import Human
    from jobos_runner.page_ops import PageOps

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=CHROME)
            pg = await b.new_page()
            await pg.goto((FIX / "groups.html").as_uri())
            fp = await PageOps(pg, Human(pg, slow=False), Path(".")).extract()
            await b.close()
            return fp

    fp = asyncio.run(run())
    by_label = {f.label: f for f in fp.fields}
    deg = by_label["Degree Type"]
    assert deg.type == "multiselect" and deg.options == ["Undergraduate/Bachelor's", "Master's", "PhD"]
    assert by_label["I agree to the privacy policy"].type == "checkbox"
    assert len([f for f in fp.fields if f.label == "Degree Type"]) == 1


@pytest.mark.skipif(not CHROME, reason="no Chromium")
def test_file_upload_required_from_container_label() -> None:
    """Greenhouse hides the input's own label ("Attach"); the asterisk lives on the container label."""
    from playwright.async_api import async_playwright

    from jobos_runner.human import Human
    from jobos_runner.page_ops import PageOps

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=CHROME)
            pg = await b.new_page()
            await pg.goto((FIX / "uploads.html").as_uri())
            fp = await PageOps(pg, Human(pg, slow=False), Path(".")).extract()
            await b.close()
            return fp

    req = {f.label: f.required for f in asyncio.run(run()).fields if f.type == "file"}
    assert req == {"Resume/CV": True, "Cover Letter": False, "Please provide a recent transcript": True}


def test_search_queries_for_long_names() -> None:
    from jobos_runner.page_ops import distinctive_token, search_queries

    v = "Indian Institute of Information Technology (IIIT) Raichur"
    assert distinctive_token(v) == "raichur"
    assert search_queries(v) == [v, "IIIT Raichur", "Raichur"]


@pytest.mark.skipif(not CHROME, reason="no Chromium")
def test_google_forms_extract_fill_and_locked() -> None:
    """Google Forms markup (served at a docs.google.com URL): every widget type extracts, fills and reads back;
    a sign-in-restricted form is a login page."""
    from playwright.async_api import async_playwright

    from jobos_common.forms import FieldType, FillPlan, FillValue, PageKind, ValueSource
    from jobos_runner.human import Human
    from jobos_runner.page_ops import PageOps

    html = (FIX / "gforms.html").read_text()
    url = "https://docs.google.com/forms/d/e/TEST/viewform"

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=CHROME)
            pg = await b.new_page()
            await pg.route("https://docs.google.com/**", lambda r: r.fulfill(body=html, content_type="text/html"))
            await pg.goto(url)
            ops = PageOps(pg, Human(pg, slow=False), Path("."))
            page = await ops.extract()
            by = {f.label: f for f in page.fields}
            plan = FillPlan(values=[
                FillValue(key=by["Full Name"].key, value="Aarav Mehta", source=ValueSource.profile),
                FillValue(key=by["Country"].key, value="India", source=ValueSource.profile),
                FillValue(key=by["Technical Knowledge"].key, value=["Python", "SQL"], source=ValueSource.profile),
                FillValue(key=by["Position applying for"].key, value="Backend Intern", source=ValueSource.user),
                FillValue(key=by["Why do you want this internship?"].key, value="To build.", source=ValueSource.user),
            ])
            res = await ops.fill(plan, {})
            after = {f.label: f.current_value for f in (await ops.extract(harvest=False)).fields}
            await pg.goto(url + "?locked=1")
            locked = await ops.extract()
            await b.close()
            return page, res, after, locked

    page, res, after, locked = asyncio.run(run())
    types = {f.label: (f.type, f.required) for f in page.fields}
    assert types == {"Full Name": (FieldType.text, True), "Country": (FieldType.radio, True),
                     "Technical Knowledge": (FieldType.multiselect, False),
                     "Position applying for": (FieldType.select, True),
                     "Why do you want this internship?": (FieldType.textarea, False)}
    assert next(f for f in page.fields if f.label == "Country").options == ["India", "Nepal", "Other"]
    assert page.kind == PageKind.form and [b.kind.value for b in page.buttons] == ["next"]
    assert all(r.ok for r in res.results), res.results
    assert after["Country"] == "India" and after["Technical Knowledge"] == "Python | SQL"
    assert after["Position applying for"] == "Backend Intern" and after["Full Name"] == "Aarav Mehta"
    assert locked.kind == PageKind.login
