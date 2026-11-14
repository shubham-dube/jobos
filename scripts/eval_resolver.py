"""Replay recorded real application pages through the form resolver on another model and compare answers.

Usage (from the repo root):
    uv run python scripts/eval_resolver.py --model openrouter:anthropic/claude-haiku-5.5 [--limit 20]

Compares, per field, the value the candidate model gives with the value in the recorded plan (the answers that
were filled on the live run). Deterministic answers (profile taxonomy, answer bank, user answers) are skipped
because they don't depend on the model. Prints agreement and every disagreement for manual review.
Uses real LLM calls (cost is printed).
"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from sqlalchemy import select

from jobos.config import get_settings
from jobos.db import session_scope
from jobos.db.models import Application, FormPageRecord, Job
from jobos.forms.resolver import ResolveContext, resolve_page
from jobos.llm.gateway import build_gateway
from jobos.services.candidates import get_profile
from jobos_common.forms import FormPage

LLM_SOURCES = {"profile", "generated"}  # values the model produced (taxonomy values carry basics.* refs)


def _norm(v: Any) -> str:
    if isinstance(v, list):
        return "|".join(sorted(_norm(x) for x in v))
    return " ".join(str(v).lower().split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="provider:model for form.resolve (no escalation)")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    settings = get_settings().model_copy(update={"llm_routes": {"form.resolve": args.model,
                                                                 "form.resolve.strong": args.model}})
    gw = build_gateway(settings)
    total = agree = 0
    disagreements: list[str] = []
    cost = 0.0
    with session_scope() as s:
        records = s.scalars(select(FormPageRecord).where(FormPageRecord.plan.is_not(None))
                            .order_by(FormPageRecord.created_at.desc())).all()
        seen: set[tuple[str, int]] = set()
        for r in records:
            key = (r.url, r.page_index)
            if key in seen or len(seen) >= args.limit:
                continue
            seen.add(key)
            recorded = {v["key"]: v for v in (r.plan or {}).get("values", [])
                        if v.get("source") in LLM_SOURCES and not str(v.get("source_ref", "")).startswith(
                            ("basics.", "education.", "work_authorization", "preferences.", "demographics."))}
            if not recorded:
                continue
            app = s.get(Application, r.application_id)
            job = s.get(Job, app.job_id) if app else None
            if app is None or job is None:
                continue
            rc = ResolveContext(profile=get_profile(s, app.candidate_id), candidate_id=app.candidate_id,
                                job_title=job.title, company=job.company_name, job_countries=job.countries,
                                job_id=str(job.id))
            page = FormPage.model_validate(r.page)
            page.fields = [f for f in page.fields if f.key in recorded]  # only the model-answered fields
            out = resolve_page(s, gw, page, rc, ref=f"eval:{uuid.uuid4().hex[:6]}")
            got = {v.key: v.value for v in out.plan.values}
            for k, v in recorded.items():
                total += 1
                label = next((f.label for f in page.fields if f.key == k), k)[:70]
                if k in got and _norm(got[k]) == _norm(v.get("value")):
                    agree += 1
                elif v.get("source") == "generated" and k in got:
                    agree += 1  # free text: both wrote grounded text; compared by a human, not string equality
                    disagreements.append(f"[text]  {job.company_name}: {label}\n   live: {str(v.get('value'))[:160]}\n"
                                         f"   test: {str(got[k])[:160]}")
                else:
                    reason = next((u.reason for u in out.plan.unresolved if u.key == k), "")
                    disagreements.append(f"[DIFF]  {job.company_name}: {label}\n   live: {v.get('value')!r}\n"
                                         f"   test: {got.get(k)!r} {('(asked: ' + reason + ')') if reason else ''}")
        s.rollback()  # the eval must not change answer-bank usage counts etc.
    from sqlalchemy import text

    with session_scope() as s:
        cost = float(s.execute(text("select coalesce(sum(cost_usd),0) from llm_calls where ref like 'eval:%' "
                                    "and created_at > now() - interval '1 hour'")).scalar() or 0)
    print(json.dumps({"model": args.model, "pages": len(seen), "fields": total, "agree": agree,
                      "agreement": round(agree / total, 3) if total else None, "cost_usd": round(cost, 4)}))
    print("\n".join(disagreements))


if __name__ == "__main__":
    main()
