from __future__ import annotations

import json
from pathlib import Path

from jobos.domain.settings import CandidateSettings
from jobos.forms.answer_bank import find_candidates, save_answer
from jobos.forms.gate import evaluate_gate, gate_token, verify_gate_token
from jobos.forms.resolver import ResolveContext, resolve_page
from jobos.forms.taxonomy import Ctx, map_field
from jobos.llm.fake import FakeProvider
from jobos.llm.gateway import LLMGateway
from jobos.services.candidates import get_or_create_default_candidate
from jobos_common.forms import (
    FieldResult,
    FieldType,
    FillPlan,
    FillResult,
    FillValue,
    FormField,
    FormPage,
    ValueSource,
)
from jobos_common.profile import MasterProfile

PROFILE = MasterProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/fake_profile.json").read_text()))


def f(key: str, label: str, type: FieldType = FieldType.text, options: list[str] | None = None, required: bool = True):
    return FormField(key=key, label=label, type=type, options=options or [], required=required)


def test_taxonomy_maps_identity_and_presets() -> None:
    ctx = Ctx(profile=PROFILE, resume_document_id="doc1")
    assert map_field(ctx, f("a", "First Name")).value == "Aarav"
    assert map_field(ctx, f("b", "Email", FieldType.email)).value == "aarav.mehta@example.com"
    assert map_field(ctx, f("c", "LinkedIn Profile")).value.endswith("aarav-mehta-example")
    assert map_field(ctx, f("d", "Country", FieldType.select, ["United States +1", "India +91"])).value == "India +91"
    eeo = map_field(ctx, f("e", "Gender", FieldType.select, ["Male", "Female", "I don't wish to answer"]))
    assert eeo.value == "I don't wish to answer" and eeo.source == ValueSource.preset
    assert map_field(ctx, f("g", "Resume/CV", FieldType.file)).file_ref == "doc1"
    # a single-option select that is not an acknowledgement must NOT be auto-chosen
    assert map_field(ctx, f("h", "Which office?", FieldType.select, ["London"])) is None
    ack = map_field(ctx, f("i", "By submitting I acknowledge the policy", FieldType.select, ["Acknowledge/Confirm"]))
    assert ack.value == "Acknowledge/Confirm"


def _gateway(fake: FakeProvider) -> LLMGateway:
    return LLMGateway({"fake": fake}, default_route="fake:test")


def test_resolver_validates_llm_output(session) -> None:
    cand = get_or_create_default_candidate(session)
    fake = FakeProvider()
    fake.on("form.resolve", lambda req: {"fields": [
        {"key": "q1", "action": "fill", "value": "Maybe", "source": "profile", "confidence": 0.99},  # not an option
        {"key": "q2", "action": "fill", "value": "I love it", "source": "generated", "fact_ids": ["nope"], "confidence": 0.9},
        {"key": "q3", "action": "fill", "value": "Yes", "source": "profile", "fact_ids": ["w1"], "confidence": 0.5},
        {"key": "q4", "action": "fill", "value": "3-5 years", "source": "profile", "fact_ids": ["w1"], "confidence": 0.9},
    ]})
    page = FormPage(url="https://x", fields=[
        f("q1", "Will you relocate?", FieldType.radio, ["Yes", "No"]),
        f("q2", "Why us?", FieldType.textarea),
        f("q3", "Do you know Go?", FieldType.radio, ["Yes", "No"]),
        f("q4", "Python experience", FieldType.select, ["0-1 years", "3-5 years"]),
    ])
    rc = ResolveContext(profile=PROFILE, candidate_id=cand.id, job_title="SWE", company="Acme", job_countries=["IN"])
    out = resolve_page(session, _gateway(fake), page, rc)
    assert [v.key for v in out.plan.values] == ["q4"]
    reasons = {u.key: u.reason for u in out.plan.unresolved}
    assert "not one of the options" in reasons["q1"]
    assert "citations" in reasons["q2"]
    assert "low confidence" in reasons["q3"]


def test_answer_bank_reuse_without_llm(session) -> None:
    cand = get_or_create_default_candidate(session)
    save_answer(session, cand.id, "What is your notice period?", "30 days")
    assert find_candidates(session, cand.id, "What is your notice period? *")[0].value == "30 days"
    fake = FakeProvider()
    page = FormPage(url="https://x", fields=[f("n", "What is your notice period?")])
    rc = ResolveContext(profile=PROFILE, candidate_id=cand.id, job_title="SWE", company="Acme", job_countries=["IN"])
    out = resolve_page(session, _gateway(fake), page, rc)
    assert out.plan.values[0].value == "30 days" and out.plan.values[0].source == ValueSource.answer_bank
    assert fake.calls == []  # no LLM call needed


def test_gate_blocks_on_problems_and_signs_tokens() -> None:
    plan = FillPlan(values=[FillValue(key="a", value="x", source=ValueSource.profile)])
    ok = evaluate_gate(plans=[plan], results=[FillResult(results=[FieldResult(key="a", ok=True)])],
                       settings=CandidateSettings(), ats="greenhouse", company="A", countries=[], remote=False,
                       match_score=80, legitimacy=90, submitted_today=0, submitted_company_today=0)
    assert ok.ok and ok.action == "review"
    bad = evaluate_gate(plans=[plan], results=[FillResult(results=[FieldResult(key="a", ok=False, error="x")])],
                        settings=CandidateSettings(), ats="greenhouse", company="A", countries=[], remote=False,
                        match_score=80, legitimacy=90, submitted_today=500, submitted_company_today=0)
    assert not bad.ok and len(bad.problems) == 2
    tok = gate_token("app", 1)
    assert verify_gate_token(tok, "app", 1) and not verify_gate_token(tok, "app", 2)


def test_llm_routing_precedence() -> None:
    fake = FakeProvider()
    g = LLMGateway({"openrouter": fake}, routes={"form": "openrouter:cheap", "form.generate": "openrouter:best"})
    assert g.route("form.resolve")[1] == "cheap"
    assert g.route("form.generate")[1] == "best"
    assert g.route("job.match")[1] == "anthropic/claude-haiku-5.5"


def test_name_variants() -> None:
    p = PROFILE.model_copy(deep=True)
    p.basics.middle_name, p.basics.preferred_name = "Kumar", "Aarav Mehta"
    ctx = Ctx(profile=p)
    assert map_field(ctx, f("a", "Legal First and Last Name")).value == "Aarav Kumar Mehta"
    assert map_field(ctx, f("b", "Preferred First Name")).value == "Aarav"
    assert map_field(ctx, f("c", "Preferred Last Name")).value == "Mehta"


def test_truncated_searchable_list_accepts_profile_value() -> None:
    ctx = Ctx(profile=PROFILE)
    field = f("s", "School", FieldType.select, [f"University {i}" for i in range(300)])
    field.locator["truncated"] = True
    assert map_field(ctx, field).value == "Example Institute of Technology"


def test_required_upload_uses_stored_document_or_asks(session) -> None:
    """A required transcript upload is filled from Documents (by kind), else becomes a question; a user's
    upload answer (doc:<id>) is attached as a file, never typed as text."""
    cand = get_or_create_default_candidate(session)
    fake = FakeProvider()
    page = FormPage(url="https://x", fields=[
        f("t", "Please provide a recent transcript", FieldType.file),
        f("c", "Cover Letter", FieldType.file, required=False),
    ])
    base = dict(profile=PROFILE, candidate_id=cand.id, job_title="SWE", company="Acme", job_countries=["GB"])

    out = resolve_page(session, _gateway(fake), page, ResolveContext(**base))
    assert [u.key for u in out.plan.unresolved] == ["t"] and out.plan.values == []

    out = resolve_page(session, _gateway(fake), page, ResolveContext(**base, documents={"transcript": "doc-1"}))
    assert [(v.key, v.file_ref, v.source) for v in out.plan.values] == [("t", "doc-1", ValueSource.document)]
    assert out.plan.unresolved == []

    out = resolve_page(session, _gateway(fake), page, ResolveContext(**base, extra_answers={"t": "doc:abc"}))
    v = out.plan.values[0]
    assert (v.key, v.value, v.file_ref, v.source_ref) == ("t", None, "abc", "document:user_upload")
    assert fake.calls == []
