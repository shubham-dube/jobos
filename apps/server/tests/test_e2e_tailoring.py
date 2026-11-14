"""E2E (spec 0002 AC5/AC7/AC9): with tailoring on, the runner uploads the job's tailored resume and a grounded
cover letter, and the review shows both."""

from __future__ import annotations

from typing import Any

from .test_e2e_apply import resolve_handler


def tailor_handler(req: Any) -> dict[str, Any]:
    return {
        "keywords": ["FastAPI", "PostgreSQL"],
        "experience": [
            {"id": "w1", "bullets": [
                {"text": "Built a FastAPI service processing 50k documents per day on PostgreSQL and Redis.",
                 "sources": ["w1h1"]},
                {"text": "Shipped an LLM-powered summarization feature used by 3 internal teams.", "sources": ["w1h2"]},
            ]},
            {"id": "w2", "bullets": [{"text": "Built two Flutter apps published on Google Play using BLoC.",
                                      "sources": ["w2h1"]}]},
        ],
        "projects": [{"id": "p1", "bullets": [{"text": "Implemented retrieval with FAISS and hybrid search.",
                                              "sources": ["p1h1"]}]}],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
    }


def cover_handler(req: Any) -> dict[str, Any]:
    claim = {"kind": "claim", "sources": ["w1h1"],
             "text": "At Acme Labs I built a FastAPI service that processes 50k documents per day."}
    return {"greeting": "Dear Hiring Team,", "closing": "Sincerely,", "paragraphs": [
        [{"kind": "context", "text": "Tailor Corp is hiring a Backend Engineer."}, claim],
        [{"kind": "claim", "sources": ["w1h2"],
          "text": "I shipped an LLM-powered summarization feature used by 3 internal teams."},
         {"kind": "claim", "sources": ["w2h1"], "text": "I also built two Flutter apps published on Google Play."}],
    ]}


def test_tailored_resume_and_cover_letter_are_uploaded(e2e_stack) -> None:
    from sqlalchemy import select

    from jobos.db import session_scope
    from jobos.db.models import FormPageRecord

    st = e2e_stack
    c = st.api
    st.fake.on("form.resolve", resolve_handler)
    st.fake.on("tailor.resume", tailor_handler)
    st.fake.on("tailor.verify", lambda req: {"results": [{"index": 0, "faithful": True}]})
    st.fake.on("tailor.cover_letter", cover_handler)
    original = c.get("/api/v1/settings").json()
    c.put("/api/v1/settings", json={**original, "tailoring": {"enabled": True, "cover_letter": "always"}}
          ).raise_for_status()
    try:
        job_id = st.add_job("job.html", "Backend Engineer", "Tailor Corp")
        app_id = c.post(f"/api/v1/jobs/{job_id}/apply").json()["application_id"]

        def review_or_answer():
            iv = st.open_iv("missing_answer", app_id)
            if iv:  # salary / transcript, depending on what earlier tests left in the answer bank
                answers = {}
                for q in iv["payload"]["questions"]:
                    if q["type"] == "file":
                        doc = c.post("/api/v1/documents", files={"file": ("t.pdf", b"%PDF-1.4 t", "application/pdf")},
                                     data={"kind": "transcript", "is_default": "true"}).json()
                        answers[q["key"]] = f"doc:{doc['id']}"
                    else:
                        answers[q["key"]] = "80000"
                c.post(f"/api/v1/interventions/{iv['id']}/answer", json={"answers": answers}).raise_for_status()
                return None
            return st.open_iv("review_before_submit", app_id)

        iv = st.wait(review_or_answer, app_id, timeout=240)
        docs = iv["payload"]["documents"]
        assert docs["resume"]["tailored"] and docs["resume"]["reworded"] == 1
        events = [e for e in c.get(f"/api/v1/applications/{app_id}").json()["events"] if e.get("actor") == "tailor"]
        assert docs["cover_letter_id"], events
        assert iv["payload"]["gate"]["facts"]["tailored_resume"] is True
        assert iv["payload"]["gate"]["facts"]["generated_cover_letter"] is True

        job = c.get(f"/api/v1/jobs/{job_id}").json()
        kinds = {d["generator"]: d for d in job["documents"]}
        assert set(kinds) == {"tailored_resume", "cover_letter"}
        meta = c.get(f"/api/v1/documents/{kinds['tailored_resume']['id']}").json()["meta"]
        assert meta["pages"] == 1 and any(d["status"] == "reworded" for d in meta["diff"])
        pdf = c.get(f"/api/v1/documents/{kinds['tailored_resume']['id']}/file")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

        c.post(f"/api/v1/interventions/{iv['id']}/answer", json={"decision": "approve"}).raise_for_status()
        st.wait(lambda: c.get(f"/api/v1/applications/{app_id}").json()["state"] == "submitted", app_id)

        # the runner really attached the generated files (read back from the browser)
        with session_scope() as s:
            actual = [r.get("actual") for p in s.scalars(select(FormPageRecord).where(
                FormPageRecord.application_id == app_id)) for r in (p.fill_result or {}).get("results", [])]
        assert any(isinstance(a, str) and a.endswith("_Resume_Tailor_Corp.pdf") for a in actual), actual
        assert any(isinstance(a, str) and a.endswith("_Cover_Letter_Tailor_Corp.pdf") for a in actual), actual
        # job-specific documents are not offered as defaults elsewhere
        assert all(d["label"] != "Tailored · Tailor Corp" for d in c.get("/api/v1/documents").json())
    finally:
        c.put("/api/v1/settings", json=original).raise_for_status()
