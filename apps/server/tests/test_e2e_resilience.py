"""E2E resilience: an exhausted LLM budget pauses an application (and it resumes by itself); an unexpected error
ends it as 'failed' with the reason — never stuck 'in progress'."""

from __future__ import annotations

from typing import Any

from .test_e2e_apply import resolve_handler


def test_budget_pause_then_resume_and_crash_guard(e2e_stack, monkeypatch) -> None:
    from jobos.llm import BudgetExceeded
    from jobos.workflows import application as wf

    st = e2e_stack
    c = st.api
    monkeypatch.setattr(wf, "BUDGET_WAIT_S", 2)

    calls = {"n": 0}

    def budget_then_ok(req: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise BudgetExceeded("daily LLM budget reached ($2.01 / $2.00)")
        return resolve_handler(req)

    st.fake.on("form.resolve", budget_then_ok)
    job_id = st.add_job("job.html", "Resilient Engineer", "Budget Corp")
    app_id = c.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": True}).json()["application_id"]

    def progressed():
        d = c.get(f"/api/v1/applications/{app_id}").json()
        if st.open_iv("missing_answer", app_id):
            return d
        return d if d["state"] in ("skipped", "failed", "needs_input") else None

    d = st.wait(progressed, app_id, timeout=180)
    assert d["state"] != "failed", d["error"]
    assert any((e.get("data") or {}).get("event") == "llm.budget_wait" for e in d["events"])
    assert calls["n"] >= 2  # it retried after the pause
    c.post(f"/api/v1/applications/{app_id}/cancel")  # don't leave a workflow waiting for an answer

    def boom(req: Any) -> dict[str, Any]:
        raise RuntimeError("provider exploded")

    st.fake.on("form.resolve", boom)
    job2 = st.add_job("job.html", "Crashy Engineer", "Crash Corp")
    app2 = c.post(f"/api/v1/jobs/{job2}/apply", json={"dry_run": True}).json()["application_id"]
    d2 = st.wait(lambda: (lambda d: d if d["state"] == "failed" else None)(
        c.get(f"/api/v1/applications/{app2}").json()), app2, timeout=180)
    assert "internal error" in d2["error"] and "provider exploded" in d2["error"]
