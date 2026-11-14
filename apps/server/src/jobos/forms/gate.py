"""Submit gate (form-filling-engine.md §8, ADR-0015). The only path to a final submit."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from jobos.config import get_settings
from jobos.domain.settings import CandidateSettings, GateFacts, decide
from jobos_common.forms import FillPlan, FillResult, ValueSource


@dataclass
class GateDecision:
    ok: bool  # hard checks passed
    action: str  # auto_submit | review | blocked
    rule: str
    problems: list[str] = field(default_factory=list)
    facts: GateFacts | None = None

    def to_json(self) -> dict:
        return {"ok": self.ok, "action": self.action, "rule": self.rule, "problems": self.problems,
                "facts": self.facts.model_dump() if self.facts else None}


def evaluate_gate(*, plans: list[FillPlan], results: list[FillResult], settings: CandidateSettings, ats: str,
                  company: str, countries: list[str], remote: bool, match_score: int | None,
                  legitimacy: int | None, submitted_today: int, submitted_company_today: int,
                  platform_native: bool = False, tailored_resume_id: str = "", tailored_rephrased: int = 0,
                  generated_cover_letter_id: str = "") -> GateDecision:
    problems: list[str] = []
    for p in plans:
        for u in p.unresolved:
            if u.required:
                problems.append(f"unanswered required field: {u.label}")
    for r in results:
        for fr in r.results:
            if not fr.ok:
                problems.append(f"field {fr.key} not filled correctly: {fr.error}")
    if results and results[-1].page and results[-1].page.errors:
        problems.append("page shows validation errors: " + "; ".join(results[-1].page.errors[:3]))
    if submitted_today >= settings.pacing.daily_cap:
        problems.append(f"daily cap reached ({settings.pacing.daily_cap})")
    if submitted_company_today >= settings.pacing.per_company_daily_cap:
        problems.append(f"per-company daily cap reached for {company}")
    values = [v for p in plans for v in p.values]
    attached = {v.file_ref for v in values if v.file_ref}
    tailored = bool(tailored_resume_id) and tailored_resume_id in attached
    facts = GateFacts(
        ats=ats, company=company, countries=countries, remote=remote, match_score=match_score,
        legitimacy=legitimacy,
        generated_fields=sum(1 for v in values if v.source == ValueSource.generated),
        low_confidence_fields=sum(1 for v in values if v.confidence < 0.9),
        answer_sources=sorted({v.source.value for v in values}),
        platform_native=platform_native,
        tailored_resume=tailored, tailored_rephrased=tailored_rephrased if tailored else 0,
        generated_cover_letter=bool(generated_cover_letter_id) and generated_cover_letter_id in attached,
    )
    if problems:
        return GateDecision(ok=False, action="blocked", rule="hard_checks", problems=problems, facts=facts)
    action, rule = decide(settings.approval_rules, facts)
    return GateDecision(ok=True, action=action, rule=rule, facts=facts)


def gate_token(application_id: str, attempt: int) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"submit:{application_id}:{attempt}".encode(), hashlib.sha256).hexdigest()


def verify_gate_token(token: str, application_id: str, attempt: int) -> bool:
    return hmac.compare_digest(token, gate_token(application_id, attempt))
