from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobos.domain.settings import ApprovalRule, GateFacts, RuleConditions, SearchFilters, decide
from jobos.domain.states import AppState, InvalidTransition, check_transition
from jobos.matching.geo import countries_for, is_remote
from jobos.matching.rules import apply_filters, assess_eligibility, legitimacy, title_seniority
from jobos_common.profile import MasterProfile

PROFILE = MasterProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/fake_profile.json").read_text()))


def test_state_machine_blocks_double_submit_paths() -> None:
    check_transition(AppState.queued, AppState.in_progress)
    check_transition(AppState.submitting, AppState.uncertain)
    with pytest.raises(InvalidTransition):
        check_transition(AppState.submitted, AppState.submitting)
    with pytest.raises(InvalidTransition):
        check_transition(AppState.uncertain, AppState.submitting)  # uncertain is never auto-retried


def test_approval_rules_default_review_and_first_match_wins() -> None:
    facts = GateFacts(ats="greenhouse", company="Stripe", match_score=82, legitimacy=90, generated_fields=0,
                      answer_sources=["profile", "preset"])
    assert decide([], facts) == ("review", "default")
    rules = [
        ApprovalRule(name="no-ai-text", when=RuleConditions(ats_in=["greenhouse", "lever"], min_match_score=75,
                                                            max_generated_fields=0,
                                                            answer_sources_subset_of=["profile", "preset", "answer_bank"]),
                     action="auto_submit"),
    ]
    assert decide(rules, facts) == ("auto_submit", "no-ai-text")
    assert decide(rules, facts.model_copy(update={"generated_fields": 1})) == ("review", "default")
    assert decide(rules, facts.model_copy(update={"ats": "workday"})) == ("review", "default")


@pytest.mark.parametrize(("loc", "expected"), [
    ("Bengaluru, Karnataka, India", {"IN"}),
    ("Austin, TX", {"US"}),
    ("London, UK", {"GB"}),
    ("Zürich, Switzerland", {"CH"}),
    ("Remote - EMEA", None),  # region expands to many countries
])
def test_geo(loc: str, expected: set[str] | None) -> None:
    got = countries_for(loc)
    if expected is None:
        assert "GB" in got and "IN" not in got
    else:
        assert got == expected


def test_remote_detection() -> None:
    assert is_remote("Remote, Global")
    assert not is_remote("San Francisco, CA")


@pytest.mark.parametrize(("title", "level"), [
    ("Software Engineer 3", "senior"), ("Software Engineer II", "mid"), ("Software Engineer I", "junior"),
    ("Software Engineer (New Grad)", "junior"), ("Backend Intern, Summer 2027", "intern"), ("Staff Engineer", "staff"),
    ("AI Engineer", "mid"), ("Engineering Manager", "senior"),
])
def test_seniority(title: str, level: str) -> None:
    assert title_seniority(title) == level


def test_eligibility_for_indian_citizen() -> None:
    assert assess_eligibility(PROFILE, ["IN"], "onsite", "", ["Pune"]).status == "home_country"
    e = assess_eligibility(PROFILE, ["US"], "onsite", "We are unable to sponsor visas for this role.", ["NYC"])
    assert not e.eligible and e.status == "no_sponsorship"
    e = assess_eligibility(PROFILE, ["GB"], "onsite", "Visa sponsorship is available for this position.", ["London"])
    assert e.eligible and e.status == "sponsorship_offered"
    assert assess_eligibility(PROFILE, [], "remote", "", ["Remote, Global"]).status == "remote_ok"
    e = assess_eligibility(PROFILE, ["US"], "remote", "", ["Remote - US"])
    assert not e.eligible and e.status == "remote_restricted"


def test_filters() -> None:
    f = SearchFilters(keywords_any=["engineer"], countries=["IN"], seniority_max="mid", posted_within_days=30)
    elig = assess_eligibility(PROFILE, ["IN"], "onsite", "", ["Pune"])
    ok = apply_filters(f, title="Backend Engineer", company="X", countries=["IN"], remote_type="onsite",
                       posted_at=datetime.now(UTC), eligibility=elig)
    assert ok.passed
    bad = apply_filters(f, title="Senior Backend Engineer", company="X", countries=["DE"], remote_type="onsite",
                        posted_at=datetime.now(UTC) - timedelta(days=90), eligibility=elig)
    assert not bad.passed and len(bad.reasons) == 3


def test_legitimacy_scores() -> None:
    good, _ = legitimacy(source="greenhouse", ats="greenhouse", posted_at=datetime.now(UTC), description="x" * 500)
    scam, reasons = legitimacy(source="other", ats="unknown", posted_at=None,
                               description="Pay a registration fee and contact us on Telegram " + "x" * 300)
    assert good >= 90 and scam < 20 and any("Scam" in r for r in reasons)
