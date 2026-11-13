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
    assert gh.apply_url == "https://job-boards.greenhouse.io/embed/job_app?for=acme&token=1" and gh.countries == ["IN"]
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
    from jobos.db.models import Candidate, Org

    org = Org(name="isolated")
    session.add(org)
    session.flush()
    cand = Candidate(org_id=org.id, name="isolated", settings={})  # own candidate: no tasks from other tests
    session.add(cand)
    session.flush()
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


@respx.mock
def test_workday_smartrecruiters_workable_sources_and_hydration() -> None:
    from jobos.sources.ats import SmartRecruitersSource, WorkableSource, WorkdaySource

    tok = "acme.wd5.myworkdayjobs.com|acme|External"
    respx.post("https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/External/jobs").mock(return_value=httpx.Response(200, json={
        "total": 1, "jobPostings": [{"title": "Software Engineer", "externalPath": "/job/India-Bengaluru/Software-Engineer_JR1",
                                     "locationsText": "India, Bengaluru", "postedOn": "Posted 3 Days Ago", "bulletFields": ["JR1"]}]}))
    respx.get("https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/External/job/India-Bengaluru/Software-Engineer_JR1").mock(
        return_value=httpx.Response(200, json={"jobPostingInfo": {"jobDescription": "<p>Build APIs</p>", "startDate": "2026-11-10",
                                                                  "country": {"descriptor": "India"}}}))
    wd = WorkdaySource().fetch(tok, "Acme")
    assert wd[0].countries == ["IN"] and wd[0].raw["needs_hydrate"]
    assert wd[0].apply_url == "https://acme.wd5.myworkdayjobs.com/External/job/India-Bengaluru/Software-Engineer_JR1/apply"
    assert WorkdaySource().hydrate(tok, wd[0].raw)["description_text"] == "Build APIs"

    respx.get("https://api.smartrecruiters.com/v1/companies/Acme/postings?limit=100&offset=0").mock(return_value=httpx.Response(200, json={
        "totalFound": 1, "content": [{"id": "9", "name": "Backend Engineer", "location": {"city": "Zurich", "country": "ch"},
                                      "releasedDate": "2026-11-10T00:00:00Z"}]}))
    sr = SmartRecruitersSource().fetch("Acme", "Acme")
    assert sr[0].countries == ["CH"] and sr[0].apply_url == "https://jobs.smartrecruiters.com/Acme/9"

    respx.get("https://apply.workable.com/api/v1/widget/accounts/acme?details=true").mock(return_value=httpx.Response(200, json={
        "name": "Acme", "jobs": [{"title": "ML Engineer", "shortcode": "AB12", "url": "https://apply.workable.com/j/AB12",
                                  "application_url": "https://apply.workable.com/j/AB12/apply", "telecommuting": True,
                                  "locations": [{"city": "Paris", "country": "France", "countryCode": "FR"}],
                                  "description": "<p>Models</p>", "published_on": "2026-11-01"}]}))
    wk = WorkableSource().fetch("acme", "Acme")
    assert wk[0].remote_type == "remote" and wk[0].description_text == "Models" and not wk[0].raw["needs_hydrate"]


def test_detect_more_ats_urls() -> None:
    assert detect_ats_from_url("https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site/job/x_JR1") == (
        "workday", "salesforce.wd12.myworkdayjobs.com|salesforce|External_Career_Site")
    assert detect_ats_from_url("https://jobs.smartrecruiters.com/ServiceNow/7440001") == ("smartrecruiters", "ServiceNow")
    assert detect_ats_from_url("https://apply.workable.com/huggingface/j/AB12/") == ("workable", "huggingface")
