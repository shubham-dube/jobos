"""Grounded tailoring (spec 0002): grounding checker, assembly, verifier, rendering, cover letters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobos.llm.fake import FakeProvider
from jobos.llm.gateway import LLMGateway
from jobos.tailoring.cover_letter import check_letter
from jobos.tailoring.grounding import check_line
from jobos.tailoring.model import Bullet, CoverLetter, ResumeVariant, Sentence, VariantItem
from jobos.tailoring.render import page_count, pdf_text, render_resume
from jobos.tailoring.sources import build_catalogue
from jobos.tailoring.tailor import tailor_resume
from jobos_common.profile import Highlight, MasterProfile, Project

PROFILE = MasterProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/fake_profile.json").read_text()))
SRC = "Built a FastAPI service that processes 50k documents per day with PostgreSQL and Redis."
JD = "Backend engineer: Python, FastAPI, PostgreSQL, distributed data pipelines, Spark. Kubernetes a plus."


def _vocab() -> set[str]:
    cat = build_catalogue(PROFILE)
    return cat.items["w1"].vocab | cat.global_vocab


@pytest.mark.parametrize(("text", "ok", "why"), [
    ("Built a FastAPI service processing 50k documents per day on PostgreSQL and Redis.", True, ""),
    ("Developed a Python FastAPI service handling 50k documents daily with PostgreSQL and Redis.", True, ""),
    ("Built a FastAPI service that processes 500k documents per day with PostgreSQL and Redis.", False, "number"),
    ("Built a FastAPI service on Spark processing 50k documents per day.", False, "term"),
    ("Led a team building a FastAPI service for 50k documents per day.", False, "role-escalating"),
    ("Architected a FastAPI service that processes 50k documents per day.", False, "role-escalating"),
    ("Built a FastAPI service. " * 8, False, "longer"),
])
def test_grounding_checker(text: str, ok: bool, why: str) -> None:
    v = check_line(text, SRC, _vocab())
    assert v.ok is ok, v.reason
    assert why in v.reason


def test_grounding_accepts_singular_plural_of_source_terms() -> None:
    assert check_line("Built local-first chat over WebSocket with offline sync.",
                      "WhatsApp-style local-first chat (WebSockets, Isar, offline/delta sync).", set()).ok


def _gateway(fake: FakeProvider) -> LLMGateway:
    return LLMGateway({"fake": fake}, default_route="fake:test")


def test_tailor_assembles_grounded_variant_and_falls_back_per_line() -> None:
    fake = FakeProvider()
    fake.on("tailor.resume", lambda req: {
        "keywords": ["Python", "FastAPI"],
        "summary": {"text": "Engineer who built a FastAPI service for 50k documents per day.", "sources": ["w1h1"]},
        "experience": [
            {"id": "w2", "bullets": [{"text": "Built two Flutter apps published on Google Play using BLoC.",
                                      "sources": ["w2h1"]}]},
            {"id": "w1", "bullets": [
                {"text": "Developed a Python FastAPI service handling 50k documents daily with PostgreSQL and Redis.",
                 "sources": ["w1h1"]},
                {"text": "Shipped an LLM summarization feature on Kubernetes used by 30 teams.", "sources": ["w1h2"]},
                {"text": "Line citing another item's fact.", "sources": ["w2h1"]},
            ]},
            {"id": "nope", "bullets": []},
        ],
        "projects": [{"id": "p1", "bullets": [{"text": "Implemented retrieval with FAISS and hybrid search.",
                                              "sources": ["p1h1"]}]}],
        "skills": ["fastapi", "Python", "Spark"],
        "awards": ["a1", "zzz"],
    })
    fake.on("tailor.verify", lambda req: {"results": [{"index": 0, "faithful": True}]})
    r = tailor_resume(_gateway(fake), PROFILE, title="Backend Engineer", company="Acme", description=JD)

    v = r.variant
    assert [e.id for e in v.experience] == ["w1", "w2"]  # reverse-chronological, unknown id ignored
    w1 = v.experience[0].bullets
    assert w1[0].text.startswith("Developed a Python FastAPI") and w1[0].sources == ["w1h1"]
    # inflated line (Kubernetes, 30 teams) reverted to the source; foreign-source line dropped
    assert w1[1].text == "Shipped an LLM-powered summarization feature used by 3 internal teams."
    assert len(w1) == 2
    assert v.skills == ["FastAPI", "Python"] and r.grounding.dropped_skills == 1
    assert v.awards == ["a1"]
    assert v.summary is not None and v.summary.sources == ["w1h1"]
    statuses = {d.final_text[:20]: d.status for d in r.diff}
    assert "kept_original" in statuses.values() and "reworded" in statuses.values()
    rejected = next(d for d in r.diff if d.status == "kept_original")
    assert "number" in rejected.reason or "term" in rejected.reason
    # every line on the page traces to an existing fact
    facts = build_catalogue(PROFILE).facts
    assert all(s in facts for it in [*v.experience, *v.projects] for b in it.bullets for s in b.sources)


def test_verifier_reverts_unfaithful_rewording() -> None:
    fake = FakeProvider()
    fake.on("tailor.resume", lambda req: {"experience": [{"id": "w1", "bullets": [
        {"text": "Built a FastAPI service processing 50k documents per day on PostgreSQL and Redis.",
         "sources": ["w1h1"]}]}]})
    fake.on("tailor.verify", lambda req: {"results": [{"index": 0, "faithful": False, "issue": "scope"}]})
    r = tailor_resume(_gateway(fake), PROFILE, title="Backend Engineer", company="Acme", description=JD)
    assert r.variant.experience[0].bullets[0].text == SRC
    assert r.grounding.reworded == 0 and r.grounding.rejected == 1
    assert r.diff[0].reason.startswith("verifier")


def test_rewording_disabled_and_llm_failure_fallback() -> None:
    fake = FakeProvider()
    fake.on("tailor.resume", lambda req: {"experience": [{"id": "w1", "bullets": [
        {"text": "Something reworded about 50k documents and FastAPI.", "sources": ["w1h1"]}]}]})
    r = tailor_resume(_gateway(fake), PROFILE, title="x", company="y", description=JD, rephrase=False)
    assert r.variant.experience[0].bullets[0].text == SRC and r.grounding.reworded == 0

    broken = FakeProvider()  # no handler → the call fails → keyword fallback, all verbatim
    r = tailor_resume(_gateway(broken), PROFILE, title="Backend Engineer", company="y", description=JD)
    assert not r.used_llm and r.grounding.reworded == 0 and r.variant.experience
    assert r.variant.skills[0] in {"Python", "FastAPI", "PostgreSQL", "Kubernetes"}


def test_render_is_text_pdf_and_trims_to_one_page() -> None:
    long = PROFILE.model_copy(deep=True)
    long.projects = [Project(id=f"x{i}", name=f"Project {i}", highlights=[
        Highlight(id=f"x{i}h{j}", text="Implemented retrieval with FAISS and hybrid search across many sources. " * 3)
        for j in range(3)]) for i in range(12)]
    variant = ResumeVariant(
        experience=[VariantItem(id="w1", bullets=[Bullet(text=SRC, sources=["w1h1"])])],
        projects=[VariantItem(id=p.id, bullets=[Bullet(text=h.text, sources=[h.id]) for h in p.highlights])
                  for p in long.projects],
        skills=["Python", "FastAPI"], awards=["a1"])
    out = render_resume(long, variant, paper="a4", max_pages=1)
    assert out.pages == 1 == page_count(out.pdf) and out.trimmed
    text = pdf_text(out.pdf)
    assert PROFILE.basics.full_name in text and "50k documents" in text
    assert sum(len(p.bullets) for p in out.variant.projects) < 36


def test_render_does_not_interpret_markup_from_data() -> None:
    p = PROFILE.model_copy(deep=True)
    p.work[0].highlights[0].text = 'Wrote #set page(paper: "a6") and *bold* $x$ <tag> @ref [link] safely.'
    v = ResumeVariant(experience=[VariantItem(id="w1", bullets=[Bullet(text=p.work[0].highlights[0].text,
                                                                       sources=["w1h1"])])])
    out = render_resume(p, v)
    assert '#set page(paper: "a6")' in pdf_text(out.pdf).replace("\n", " ")


def test_cover_letter_drops_ungrounded_sentences() -> None:
    letter = CoverLetter(paragraphs=[[
        Sentence(kind="context", text="Acme is building distributed data pipelines in Python."),
        Sentence(kind="claim", text="At Acme Labs I built a FastAPI service that processes 50k documents per day.",
                 sources=["w1h1"]),
        Sentence(kind="claim", text="I scaled it to 5 million documents per day on Kubernetes.", sources=["w1h1"]),
        Sentence(kind="claim", text="I also know Spark well.", sources=[]),
        Sentence(kind="context", text="I have 6 years of Python experience."),
    ]])
    res = check_letter(letter, PROFILE, title="Backend Engineer", company="Acme", description=JD)
    assert res.kept == 2 and len(res.dropped) == 3
    assert "50k documents" in res.paragraphs[0] and "5 million" not in res.paragraphs[0]


def test_summary_may_use_readable_dates_of_cited_facts() -> None:
    from jobos.tailoring.tailor import DraftBullet as B
    from jobos.tailoring.tailor import TailorDraft, assemble

    cat = build_catalogue(PROFILE)
    draft = TailorDraft(summary=B(text="Computer Science student graduating May 2027 who built a FastAPI service.",
                                  sources=["e1", "w1h1"]),
                        experience=[{"id": "w1", "bullets": [{"text": SRC, "sources": ["w1h1"]}]}])
    r = assemble(PROFILE, cat, draft, rephrase=True)
    assert r.variant.summary is not None, r.grounding.notes
    bad = TailorDraft(summary=B(text="Student graduating June 2027.", sources=["e1"]))
    assert assemble(PROFILE, cat, bad, rephrase=True).variant.summary is None


def test_values_filled_in_earlier_passes_stay_in_the_evidence() -> None:
    """Greenhouse swaps a file input for a filename chip once attached; a retry pass re-extracts the page without
    it. The final plan/results must still show the (tailored) resume we attached in pass 1."""
    from jobos.workflows.application import _carry_forward

    filled: dict = {}
    p1 = {"values": [{"key": "id:resume", "file_ref": "doc-1"}, {"key": "id:city", "value": "Raichur"}]}
    f1 = {"results": [{"key": "id:resume", "ok": True, "actual": "R.pdf"}, {"key": "id:city", "ok": False}]}
    _carry_forward(p1, f1, filled)
    p2 = {"values": [{"key": "id:city", "value": "Raichur, Karnataka"}]}  # resume field gone from the page
    f2 = {"results": [{"key": "id:city", "ok": True}]}
    _carry_forward(p2, f2, filled)
    assert [v["key"] for v in p2["values"]] == ["id:city", "id:resume"]
    assert {r["key"] for r in f2["results"]} == {"id:city", "id:resume"}
    assert p2["values"][0]["value"] == "Raichur, Karnataka"  # newer pass wins
