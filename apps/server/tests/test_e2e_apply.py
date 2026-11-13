"""End-to-end: API + DBOS workflows + real runner + headless browser + fake ATS (LLM faked).

Covers: navigation from a job page, cookie banner, multi-page form, autocomplete, radio group, file upload,
grounded generated answer, missing answer → intervention → answer bank, review → approve, submit, evidence,
recipe learning.
"""

from __future__ import annotations

import asyncio
import functools
import glob
import http.server
import json
import os
import re
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CHROME = os.environ.get("JOBOS_TEST_CHROME") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")), "")

pytestmark = pytest.mark.browser


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_static(directory: Path) -> tuple[str, http.server.ThreadingHTTPServer]:
    port = _free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}", httpd


def _fake_llm_handlers(fake) -> None:
    def resolve(req):
        prompt = req.messages[-1].content
        m = re.search(r'<untrusted source="form_fields">\n(.*?)\n</untrusted>', prompt, re.S)
        fields = json.loads(m.group(1)) if m else []
        out = []
        for f in fields:
            k = f["key"]
            if k == "id:years":
                out.append({"key": k, "action": "fill", "value": "1-3 years", "source": "profile",
                            "fact_ids": ["w1", "w2"], "confidence": 0.85})
            elif k == "id:why":
                out.append({"key": k, "action": "fill", "source": "generated", "fact_ids": ["w1h1"], "confidence": 0.9,
                            "value": "I build FastAPI services on PostgreSQL every day and want to do it at Example Corp."})
            elif "sponsor" in k:
                out.append({"key": k, "action": "fill", "value": "Yes", "source": "profile", "fact_ids": [],
                            "confidence": 0.95})
            else:
                out.append({"key": k, "action": "ask", "confidence": 0.0, "question_for_user": f"Please answer: {f['label']}"})
        return {"fields": out}

    fake.on("form.resolve", resolve)


@pytest.mark.skipif(not CHROME, reason="no Chromium available")
def test_full_application_flow(tmp_path: Path) -> None:
    from jobos.db import session_scope
    from jobos.db.models import Company, Job, SiteRecipe
    from jobos.domain.settings import ActiveHours, CandidateSettings, Pacing
    from jobos.llm import get_gateway
    from jobos.services.candidates import get_or_create_default_candidate, save_candidate_settings, save_profile
    from jobos_common.profile import MasterProfile

    site, httpd = _serve_static(FIXTURES / "fake_ats")
    _fake_llm_handlers(get_gateway().providers["fake"])

    # --- data: profile, settings (no pacing delays), job ---------------------------------------
    with session_scope() as s:
        cand = get_or_create_default_candidate(s)
        save_profile(s, cand.id, MasterProfile.model_validate(json.loads((FIXTURES / "fake_profile.json").read_text())))
        from datetime import time as dtime

        save_candidate_settings(s, cand.id, CandidateSettings(pacing=Pacing(
            min_gap_seconds=0, max_gap_seconds=0, active_hours=ActiveHours(start=dtime(0, 0), end=dtime(23, 59, 59)))))
        comp = Company(name="Example Corp", normalized_name="example corp", ats="unknown", board_token="example")
        s.add(comp)
        s.flush()
        job = Job(company_id=comp.id, company_name="Example Corp", source="test", source_job_id="1",
                  url=f"{site}/job.html", apply_url=f"{site}/job.html", ats="unknown", title="Backend Engineer",
                  title_norm="backend engineer", countries=["US"], remote_type="onsite", fingerprint="x")
        s.add(job)
        s.flush()
        job_id = str(job.id)

    # --- API server with workers ----------------------------------------------------------------
    import uvicorn

    from jobos.api.app import create_app

    api_port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(launch_workers=True), host="127.0.0.1", port=api_port,
                                           log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    api = f"http://127.0.0.1:{api_port}"
    h = {"Authorization": "Bearer test-token"}
    for _ in range(100):
        try:
            if httpx.get(f"{api}/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)

    c = httpx.Client(base_url=api, headers=h, timeout=30)
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 fake resume")
    assert c.post("/api/v1/documents", files={"file": ("resume.pdf", resume.read_bytes(), "application/pdf")},
                  data={"label": "Backend", "is_default": "true"}).status_code == 200
    token = c.post("/api/v1/runners", json={"name": "test-runner"}).json()["token"]

    # --- runner ---------------------------------------------------------------------------------
    from jobos_runner.agent import RunnerAgent
    from jobos_runner.config import RunnerConfig

    cfg = RunnerConfig(api_url=api, token=token, profile_dir=str(tmp_path / "profile"), browser_channel="",
                       executable_path=CHROME, headless=True, max_sessions=1, slow_typing=False,
                       downloads_dir=str(tmp_path / "files"))
    agent = RunnerAgent(cfg, log=lambda *_: None)
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_until_complete, args=(agent.run(),), daemon=True).start()

    try:
        app_id = c.post(f"/api/v1/jobs/{job_id}/apply").json()["application_id"]

        def wait_for(pred, timeout=120):
            end = time.time() + timeout
            while time.time() < end:
                v = pred()
                if v:
                    return v
                time.sleep(0.5)
            detail = c.get(f"/api/v1/applications/{app_id}").json()
            raise AssertionError(f"timeout; app={detail['state']} err={detail['error']} events={detail['events'][-3:]}")

        def open_iv(kind):
            ivs = [i for i in c.get("/api/v1/interventions").json() if i["kind"] == kind]
            return ivs[0] if ivs else None

        # 1) salary is unknown → the agent asks
        iv = wait_for(lambda: open_iv("missing_answer"))
        keys = [q["key"] for q in iv["payload"]["questions"]]
        assert keys == ["id:salary"], keys
        r = c.post(f"/api/v1/interventions/{iv['id']}/answer",
                   json={"answers": {"id:salary": "80000"}, "remember": {"id:salary": "global"}})
        assert r.status_code == 200

        # 2) review before submit (default rule = review everything)
        iv = wait_for(lambda: open_iv("review_before_submit"), timeout=180)
        fields = {f["label"]: f for p in iv["payload"]["pages"] for f in p["fields"]}
        assert fields["Email"]["value"] == "aarav.mehta@example.com"
        assert fields["Why do you want to work at Example Corp?"]["source"] == "generated"
        assert c.post(f"/api/v1/interventions/{iv['id']}/answer", json={"decision": "approve"}).status_code == 200

        # 3) submitted with confirmation
        wait_for(lambda: c.get(f"/api/v1/applications/{app_id}").json()["state"] == "submitted", timeout=120)
        detail = c.get(f"/api/v1/applications/{app_id}").json()
        assert len(detail["pages"]) >= 3  # open + 2 form pages (+ confirmation)
        assert any(p["screenshots"] for p in detail["pages"])

        # 4) answer bank + learned recipe
        answers = c.get("/api/v1/answers").json()
        assert any(a["value"] == "80000" for a in answers)
        with session_scope() as s:
            from sqlalchemy import select

            recipe = s.scalar(select(SiteRecipe))
            assert recipe is not None and recipe.successes == 1
            assert recipe.data["nav"] == ["apply"]
            assert any(v["value"] == "80000" for v in recipe.data["fields"].values())
    finally:
        agent.stop()
        server.should_exit = True
        httpd.shutdown()
        time.sleep(1)
