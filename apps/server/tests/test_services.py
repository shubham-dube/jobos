from __future__ import annotations

import httpx
import respx

from jobos.services import runner_gateway as rg
from jobos.services.candidates import get_or_create_default_candidate
from jobos.services.secrets import decrypt, encrypt
from jobos.sources.ats import AshbySource, GreenhouseSource, LeverSource, detect_ats_from_url
from jobos_common.runner import TaskType


@respx.mock
def test_greenhouse_lever_ashby_parsing() -> None:
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true").mock(return_value=httpx.Response(200, json={
        "jobs": [{"id": 1, "title": "Backend Engineer", "absolute_url": "https://acme.com/jobs?gh_jid=1",
                  "location": {"name": "Bengaluru, India"}, "content": "&lt;p&gt;Build APIs&lt;/p&gt;",
                  "first_published": "2026-11-01T00:00:00Z", "company_name": "Acme", "departments": [{"name": "Eng"}]}]}))
    respx.get("https://api.lever.co/v0/postings/acme?mode=json").mock(return_value=httpx.Response(200, json=[
        {"id": "x", "text": "SWE", "hostedUrl": "https://jobs.lever.co/acme/x", "applyUrl": "https://jobs.lever.co/acme/x/apply",
         "categories": {"location": "London", "allLocations": ["London"], "team": "Eng", "commitment": "Full-time"},
         "workplaceType": "hybrid", "country": "GB", "createdAt": 1762000000000, "descriptionPlain": "Build things"}]))
    respx.get("https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=true").mock(return_value=httpx.Response(200, json={
        "jobs": [{"id": "y", "title": "AI Engineer", "location": "Remote", "isRemote": True, "workplaceType": "Remote",
                  "jobUrl": "https://jobs.ashbyhq.com/acme/y", "applyUrl": "https://jobs.ashbyhq.com/acme/y/application",
                  "descriptionPlain": "LLMs", "publishedAt": "2026-11-05T00:00:00Z", "isListed": True}]}))
    gh = GreenhouseSource().fetch("acme", "Acme")[0]
    assert gh.apply_url == "https://job-boards.greenhouse.io/acme/jobs/1" and gh.countries == ["IN"]
    assert gh.description_text == "Build APIs"
    lv = LeverSource().fetch("acme", "Acme")[0]
    assert lv.remote_type == "hybrid" and lv.countries == ["GB"]
    ash = AshbySource().fetch("acme", "Acme")[0]
    assert ash.remote_type == "remote"


def test_detect_ats_from_url() -> None:
    assert detect_ats_from_url("https://job-boards.greenhouse.io/stripe/jobs/123") == ("greenhouse", "stripe")
    assert detect_ats_from_url("https://jobs.lever.co/palantir/abc/apply") == ("lever", "palantir")
    assert detect_ats_from_url("https://jobs.ashbyhq.com/openai/xyz") == ("ashby", "openai")
    assert detect_ats_from_url("https://example.com/careers") is None


def test_runner_task_lease_and_submit_never_re_leased(session) -> None:
    cand = get_or_create_default_candidate(session)
    runner, token = rg.create_runner(session, cand.id, "pc")
    assert rg.runner_by_token(session, token).id == runner.id
    t1 = rg.create_task(session, candidate_id=cand.id, workflow_id="wf", idempotency_key="k1", type=TaskType.extract,
                        session_id="s", payload={})
    again = rg.create_task(session, candidate_id=cand.id, workflow_id="wf", idempotency_key="k1",
                           type=TaskType.extract, session_id="s", payload={})
    assert again.id == t1.id  # idempotent
    leased = rg.lease_next(session, runner)
    assert leased and leased.id == str(t1.id)
    from datetime import UTC, datetime, timedelta

    sub = rg.create_task(session, candidate_id=cand.id, workflow_id="wf", idempotency_key="k2", type=TaskType.submit,
                         session_id="s", payload={}, timeout_s=1)
    assert rg.lease_next(session, runner).id == str(sub.id)
    sub.leased_at = datetime.now(UTC) - timedelta(minutes=5)
    t1.leased_at = datetime.now(UTC) - timedelta(minutes=10)
    rg.expire_stale(session)
    assert sub.status == "expired" and t1.status == "pending"


def test_secret_roundtrip() -> None:
    assert decrypt(encrypt("app-password")) == "app-password"


def test_whatsapp_reply_mapping(session) -> None:
    from jobos.services.interventions import answer_from_reply, create_intervention

    cand = get_or_create_default_candidate(session)
    iv = create_intervention(session, candidate_id=cand.id, workflow_id="wf", kind="missing_answer", title="q",
                             payload={"questions": [{"key": "k", "label": "Relocate?", "options": ["Yes", "No"]}]})
    done = answer_from_reply(session, f"iv:{iv.id}:1")
    assert done is not None and done.answer["answers"] == {"k": "No"} and done.status == "answered"
