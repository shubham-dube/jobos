"""E2E: the autopilot loop with review — search profile (auto_apply) → discovery evaluates + shortlists → the
application is queued automatically → filled in the browser → waits in the review queue → bulk-approved →
submitted. Also: the daily cap stops further auto-queueing."""

from __future__ import annotations

from typing import Any

from .test_e2e_apply import resolve_handler

DESCRIPTION = ("We are hiring an Autopilot Engineer to build Python and FastAPI services on PostgreSQL. "
               "You will own backend features end to end, write tests, and work with product teams. ") * 3


def match_handler(req: Any) -> dict[str, Any]:
    return {"score": 91, "seniority_fit": "good", "reasons": ["Python/FastAPI match"], "gaps": [], "resume_label": ""}


def _answer_questions(st, c, app_id: str) -> None:
    iv = st.open_iv("missing_answer", app_id)
    if not iv:
        return
    answers = {}
    for q in iv["payload"]["questions"]:
        if q["type"] == "file":
            doc = c.post("/api/v1/documents", files={"file": ("t.pdf", b"%PDF-1.4 t", "application/pdf")},
                         data={"kind": "transcript", "is_default": "true"}).json()
            answers[q["key"]] = f"doc:{doc['id']}"
        else:
            answers[q["key"]] = "80000"
    c.post(f"/api/v1/interventions/{iv['id']}/answer", json={"answers": answers}).raise_for_status()


def test_autopilot_queues_fills_and_waits_for_bulk_review(e2e_stack) -> None:
    from sqlalchemy import update

    from jobos.db import session_scope
    from jobos.db.models import Job
    from jobos.workflows.runtime import client

    st = e2e_stack
    c = st.api
    st.fake.on("form.resolve", resolve_handler)
    st.fake.on("job.match", match_handler)
    job_id = st.add_job("job.html", "Autopilot Engineer", "Autopilot Corp")
    with session_scope() as s:  # a real-looking posting (short descriptions lower legitimacy below the queue bar)
        s.execute(update(Job).where(Job.id == job_id).values(description_text=DESCRIPTION))

    sp = c.post("/api/v1/search-profiles", json={
        "name": "autopilot", "enabled": True, "auto_apply": True, "schedule_minutes": 720,
        "filters": {"keywords_any": ["Autopilot"], "sources": ["unknown"], "countries": [],
                    "require_visa_friendly_abroad": False},
    }).json()
    run = c.post(f"/api/v1/search-profiles/{sp['id']}/run", params={"max_llm_scores": 5, "crawl": "false"}).json()
    summary = client().retrieve_workflow(run["workflow_id"]).get_result()
    assert summary["queued"] == 1, summary
    [app_id] = [a["id"] for a in c.get("/api/v1/applications").json() if a["company"] == "Autopilot Corp"]
    detail = c.get(f"/api/v1/applications/{app_id}").json()
    assert detail["events"][0]["actor"] == "auto"  # created by the autopilot, not by hand

    def in_review():
        _answer_questions(st, c, app_id)
        reviews = c.get("/api/v1/interventions", params={"kind": "review_before_submit"}).json()
        return next((r for r in reviews if r["application_id"] == app_id), None)

    iv = st.wait(in_review, app_id, timeout=240)
    assert iv["payload"]["gate"]["facts"]["match_score"] == 91
    # nothing is submitted until the human says so
    assert c.get(f"/api/v1/applications/{app_id}").json()["state"] == "ready_for_review"

    out = c.post("/api/v1/interventions/bulk", json={"ids": [iv["id"], "not-a-review"], "decision": "approve"}).json()
    assert out["answered"] == 1 and out["skipped"] == ["not-a-review"]
    st.wait(lambda: c.get(f"/api/v1/applications/{app_id}").json()["state"] == "submitted", app_id)

    # daily cap: with the cap used up, another shortlisted job is not auto-queued
    settings = c.get("/api/v1/settings").json()
    c.put("/api/v1/settings", json={**settings, "pacing": {**settings["pacing"], "daily_cap": 1}}).raise_for_status()
    try:
        job2 = st.add_job("job.html", "Autopilot Engineer II", "Autopilot Two")
        with session_scope() as s:
            s.execute(update(Job).where(Job.id == job2).values(description_text=DESCRIPTION))
        run = c.post(f"/api/v1/search-profiles/{sp['id']}/run", params={"max_llm_scores": 5, "crawl": "false"}).json()
        client().retrieve_workflow(run["workflow_id"]).get_result()  # blocks until discovery is done
        # (a scheduled discovery tick may have evaluated it first; either way it is shortlisted, not queued)
        assert c.get(f"/api/v1/jobs/{job2}").json()["status"] == "shortlisted"
        assert not [a for a in c.get("/api/v1/applications").json() if a["company"] == "Autopilot Two"]
    finally:
        c.put("/api/v1/settings", json=settings).raise_for_status()
