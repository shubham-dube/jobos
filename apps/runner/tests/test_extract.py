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
