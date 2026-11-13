"""End-to-end: API + DBOS workflows + real runner + headless browser + fake ATS (LLM faked)."""

from __future__ import annotations

import json
import re

import pytest

pytestmark = pytest.mark.browser


def resolve_handler(req):
    prompt = req.messages[-1].content
    m = re.search(r'<untrusted source="form_fields">\n(.*?)\n</untrusted>', prompt, re.S)
    fields = json.loads(m.group(1)) if m else []
    out = []
    for f in fields:
        k = f["key"]
        if k == "id:years":
            out.append({"key": k, "action": "fill", "value": "1-3 years", "source": "profile", "fact_ids": ["w1", "w2"],
                        "confidence": 0.85})
        elif k == "id:why":
            out.append({"key": k, "action": "fill", "source": "generated", "fact_ids": ["w1h1"], "confidence": 0.9,
                        "value": "I build FastAPI services on PostgreSQL every day and want to do it at Example Corp."})
        elif "sponsor" in k:
            out.append({"key": k, "action": "fill", "value": "Yes", "source": "profile", "fact_ids": [], "confidence": 0.95})
        else:
            out.append({"key": k, "action": "ask", "confidence": 0.0, "question_for_user": f"Please answer: {f['label']}"})
    return {"fields": out}


def test_full_application_flow(e2e_stack) -> None:
    from sqlalchemy import select

    from jobos.db import session_scope
    from jobos.db.models import SiteRecipe

    st = e2e_stack
    st.fake.on("form.resolve", resolve_handler)
    c = st.api
    job_id = st.add_job("job.html", "Backend Engineer", "Example Corp")
    app_id = c.post(f"/api/v1/jobs/{job_id}/apply").json()["application_id"]

    # 1) salary is unknown → the agent asks
    iv = st.wait(lambda: st.open_iv("missing_answer", app_id), app_id)
    assert [q["key"] for q in iv["payload"]["questions"]] == ["id:salary"]
    c.post(f"/api/v1/interventions/{iv['id']}/answer",
           json={"answers": {"id:salary": "80000"}, "remember": {"id:salary": "global"}}).raise_for_status()

    # 2) review before submit (default rule = review everything)
    iv = st.wait(lambda: st.open_iv("review_before_submit", app_id), app_id, timeout=180)
    fields = {f["label"]: f for p in iv["payload"]["pages"] for f in p["fields"]}
    assert fields["Email"]["value"] == "aarav.mehta@example.com"
    assert fields["Why do you want to work at Example Corp?"]["source"] == "generated"
    c.post(f"/api/v1/interventions/{iv['id']}/answer", json={"decision": "approve"}).raise_for_status()

    # 3) submitted with confirmation + evidence
    st.wait(lambda: c.get(f"/api/v1/applications/{app_id}").json()["state"] == "submitted", app_id)
    detail = c.get(f"/api/v1/applications/{app_id}").json()
    assert len(detail["pages"]) >= 3 and any(p["screenshots"] for p in detail["pages"])

    # 4) answer bank + learned recipe
    assert any(a["value"] == "80000" for a in c.get("/api/v1/answers").json())
    with session_scope() as s:
        recipe = s.scalar(select(SiteRecipe).where(SiteRecipe.site_key.like("site:127.0.0.1%")))
        assert recipe is not None and recipe.successes >= 1 and recipe.data["nav"] == ["apply"]
        assert any(v["value"] == "80000" for v in recipe.data["fields"].values())


def test_dry_run_stops_before_submit(e2e_stack) -> None:
    st = e2e_stack
    st.fake.on("form.resolve", resolve_handler)
    job_id = st.add_job("job.html", "Platform Engineer", "Dry Corp")
    app_id = st.api.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": True}).json()["application_id"]
    st.wait(lambda: st.api.get(f"/api/v1/applications/{app_id}").json()["outcome"] == "dry_run_complete", app_id)
    d = st.api.get(f"/api/v1/applications/{app_id}").json()
    assert d["state"] == "skipped" and not d["submitted_at"]
    assert not any(e["to"] == "submitting" for e in d["events"])


def test_cancel_wakes_waiting_workflow_and_queue_keeps_moving(e2e_stack) -> None:
    st = e2e_stack

    def ask_everything(req):
        out = resolve_handler(req)
        for f in out["fields"]:
            f.update(action="ask", value=None, confidence=0.0)
        return out

    st.fake.on("form.resolve", ask_everything)
    a1 = st.api.post(f"/api/v1/jobs/{st.add_job('job.html', 'Waiting Engineer', 'Wait Corp')}/apply").json()["application_id"]
    st.wait(lambda: st.open_iv("missing_answer", a1), a1)
    st.api.post(f"/api/v1/applications/{a1}/cancel").raise_for_status()
    assert st.api.get(f"/api/v1/applications/{a1}").json()["state"] == "cancelled"
    # a new application (same employer partition would be blocked if the waiting workflow kept running)
    st.fake.on("form.resolve", resolve_handler)
    a2 = st.api.post(f"/api/v1/jobs/{st.add_job('job.html', 'Next Engineer', 'Wait Corp')}/apply",
                     json={"dry_run": True}).json()["application_id"]

    def progressed():
        iv = st.open_iv("missing_answer", a2)
        if iv:
            st.api.post(f"/api/v1/interventions/{iv['id']}/answer",
                        json={"answers": {q["key"]: "80000" for q in iv["payload"]["questions"]}})
        return st.api.get(f"/api/v1/applications/{a2}").json()["outcome"] == "dry_run_complete"

    st.wait(progressed, a2, timeout=120)
