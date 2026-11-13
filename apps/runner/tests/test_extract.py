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
