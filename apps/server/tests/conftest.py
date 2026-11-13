"""Test configuration. Uses a dedicated Postgres database (JOBOS_TEST_DATABASE_URL)."""

from __future__ import annotations

import os
import secrets
import tempfile

TEST_DB = os.environ.get("JOBOS_TEST_DATABASE_URL", "postgresql+psycopg://jobos:jobos@localhost:5432/jobos_test")
os.environ.update({
    "JOBOS_ENV": "test",
    "JOBOS_DATABASE_URL": TEST_DB,
    "JOBOS_LLM_FAKE": "1",
    "JOBOS_DATA_DIR": tempfile.mkdtemp(prefix="jobos-test-"),
    "JOBOS_API_TOKEN": "test-token",
    "JOBOS_SECRET_KEY": secrets.token_hex(32),  # random per test run
    "JOBOS_INTERVENTION_TIMEOUT_H": "1",
})

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS dbos CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    from jobos.db.migrate import upgrade

    upgrade(TEST_DB)


@pytest.fixture
def session():
    from jobos.db import session_scope

    with session_scope() as s:
        yield s


# ------------------------------------------------------------------ shared e2e stack (browser tests)
import asyncio  # noqa: E402
import functools  # noqa: E402
import glob  # noqa: E402
import http.server  # noqa: E402
import json  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CHROME = os.environ.get("JOBOS_TEST_CHROME") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")), "")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class Stack:
    site: str  # fake ATS base URL
    api: object  # httpx.Client with auth
    fake: object  # FakeProvider
    tmp: Path

    def add_job(self, path: str, title: str, company: str, countries: list[str] | None = None) -> str:
        import uuid as _uuid

        from jobos.db import session_scope
        from jobos.db.models import Company, Job

        with session_scope() as s:
            comp = Company(name=company, normalized_name=company.lower(), ats="unknown", board_token=_uuid.uuid4().hex[:8])
            s.add(comp)
            s.flush()
            job = Job(company_id=comp.id, company_name=company, source="test", source_job_id=_uuid.uuid4().hex,
                      url=f"{self.site}/{path}", apply_url=f"{self.site}/{path}", ats="unknown", title=title,
                      title_norm=title.lower(), countries=countries or ["US"], remote_type="onsite",
                      fingerprint=_uuid.uuid4().hex)
            s.add(job)
            s.flush()
            return str(job.id)

    def wait(self, pred, app_id: str, timeout: float = 150):
        end = time.time() + timeout
        while time.time() < end:
            v = pred()
            if v:
                return v
            time.sleep(0.5)
        d = self.api.get(f"/api/v1/applications/{app_id}").json()
        raise AssertionError(f"timeout; state={d['state']} err={d['error']} events={d['events'][-4:]}")

    def open_iv(self, kind: str, app_id: str):
        ivs = [i for i in self.api.get("/api/v1/interventions").json()
               if i["kind"] == kind and i["application_id"] == app_id]
        return ivs[0] if ivs else None


@pytest.fixture(scope="session")
def e2e_stack(tmp_path_factory, database):
    if not CHROME:
        pytest.skip("no Chromium available")
    import httpx
    import uvicorn

    from jobos.api.app import create_app
    from jobos.db import session_scope
    from jobos.domain.settings import ActiveHours, CandidateSettings, Pacing
    from jobos.llm import get_gateway
    from jobos.services.candidates import (
        get_or_create_default_candidate,
        save_candidate_settings,
        save_profile,
    )
    from jobos_common.profile import MasterProfile
    from jobos_runner.agent import RunnerAgent
    from jobos_runner.config import RunnerConfig

    tmp = tmp_path_factory.mktemp("e2e")
    port = _free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES / "fake_ats"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    from datetime import time as dtime

    with session_scope() as s:
        cand = get_or_create_default_candidate(s)
        save_profile(s, cand.id, MasterProfile.model_validate(json.loads((FIXTURES / "fake_profile.json").read_text())))
        save_candidate_settings(s, cand.id, CandidateSettings(pacing=Pacing(
            min_gap_seconds=0, max_gap_seconds=0, active_hours=ActiveHours(start=dtime(0, 0), end=dtime(23, 59, 59)))))

    api_port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(launch_workers=True), host="127.0.0.1", port=api_port,
                                           log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{api_port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    client = httpx.Client(base_url=base, headers={"Authorization": "Bearer test-token"}, timeout=30)
    resume = tmp / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 fake resume")
    client.post("/api/v1/documents", files={"file": ("resume.pdf", resume.read_bytes(), "application/pdf")},
                data={"label": "Backend", "is_default": "true"}).raise_for_status()
    token = client.post("/api/v1/runners", json={"name": "test-runner"}).json()["token"]
    cfg = RunnerConfig(api_url=base, token=token, profile_dir=str(tmp / "profile"), browser_channel="",
                       executable_path=CHROME, headless=True, max_sessions=1, slow_typing=False,
                       downloads_dir=str(tmp / "files"))
    agent = RunnerAgent(cfg, log=lambda *_: None)
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_until_complete, args=(agent.run(),), daemon=True).start()
    yield Stack(site=f"http://127.0.0.1:{port}", api=client, fake=get_gateway().providers["fake"], tmp=tmp)
    agent.stop()
    server.should_exit = True
    httpd.shutdown()
    time.sleep(1)
