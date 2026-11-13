"""ApplicationWorkflow: open → reach form → (resolve → ask → fill → verify)* → gate → review → submit.

See docs/architecture/agents-and-workflows.md §3-5 and form-filling-engine.md.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from dbos import DBOS

from jobos.db import session_scope
from jobos.db.models import Application, Candidate, Document, FormPageRecord
from jobos.domain.states import AppState
from jobos.forms import recipes
from jobos.forms.answer_bank import mark_used, save_answer
from jobos.forms.gate import evaluate_gate, gate_token
from jobos.forms.resolver import ResolveContext, resolve_page
from jobos.llm import get_gateway
from jobos.services.applications import attempt_context, submitted_counts, transition
from jobos.services.candidates import get_candidate_settings, get_profile
from jobos_common.forms import FillPlan, FillResult, FormPage, PageKind, SubmitResult
from jobos_common.runner import TaskType

from .navigator import decide_nav_step
from .primitives import Counter, ask_human, call_runner, fire_runner

MAX_PAGES = 12
MAX_NAV_STEPS = 8


# ------------------------------------------------------------------------------------- steps --

@DBOS.step()
def start_step(app_id: str) -> dict[str, Any]:
    with session_scope() as s:
        app = s.get(Application, uuid.UUID(app_id))
        assert app is not None
        if app.state not in (AppState.queued, AppState.in_progress, AppState.needs_input,
                             AppState.ready_for_review):
            return {"skip": True, "state": app.state}
        if app.workflow_id and app.workflow_id != DBOS.workflow_id:
            return {"skip": True, "state": "superseded by a newer run"}
        app.attempt += 1
        app.workflow_id = DBOS.workflow_id or ""
        app.error = ""
        transition(s, app, AppState.in_progress, data={"attempt": app.attempt})
        ctx = attempt_context(s, app.id)
        recipes.note_job_seen(s, ctx["site_key"], ctx["ats"])
        ctx["recipe_nav"] = recipes.recipe_nav(s, ctx["site_key"])
        return ctx


@DBOS.step()
def seconds_until_active_step(candidate_id: str) -> float:
    """Human pacing: wait for active hours, plus a small random gap between applications."""
    with session_scope() as s:
        cand = s.get(Candidate, uuid.UUID(candidate_id))
        st = get_candidate_settings(s, uuid.UUID(candidate_id))
        tz = cand.timezone if cand else "Asia/Kolkata"
    now = datetime.now(UTC)
    gap = random.uniform(st.pacing.min_gap_seconds, st.pacing.max_gap_seconds)
    hours = st.pacing.active_hours
    for minutes in range(0, 7 * 24 * 60, 15):
        t = now + timedelta(minutes=minutes)
        if hours.contains(t, tz):
            return minutes * 60 + gap
    return gap


@DBOS.step()
def set_state_step(app_id: str, state: str, data: dict[str, Any] | None = None, error: str = "") -> None:
    with session_scope() as s:
        app = s.get(Application, uuid.UUID(app_id))
        assert app is not None
        if app.state == AppState.cancelled:
            return
        if error:
            app.error = error[:2000]
        transition(s, app, AppState(state), data=data)


@DBOS.step(retries_allowed=True, max_attempts=3, interval_seconds=5)
def resolve_step(ctx: dict[str, Any], page: dict[str, Any], extra_answers: dict[str, Any],
                 error_hints: dict[str, str]) -> dict[str, Any]:
    with session_scope() as s:
        cand_id = uuid.UUID(ctx["candidate_id"])
        settings = get_candidate_settings(s, cand_id)
        rc = ResolveContext(
            profile=get_profile(s, cand_id), candidate_id=cand_id, job_title=ctx["title"], company=ctx["company"],
            job_countries=ctx["countries"], job_id=ctx["job_id"], resume_document_id=ctx["resume_document_id"],
            site_key=ctx["site_key"], recipe_fields=recipes.recipe_fields(s, ctx["site_key"]),
            extra_answers=extra_answers, min_confidence=settings.thresholds.auto_answer_confidence)
        out = resolve_page(s, get_gateway(), FormPage.model_validate(page), rc,
                           ref=ctx["application_id"], error_hints=error_hints)
        mark_used(s, out.answer_ids_used)
        return out.plan.model_dump(mode="json")


@DBOS.step()
def save_answers_step(ctx: dict[str, Any], questions: list[dict[str, Any]], answer: dict[str, Any]) -> None:
    remember = answer.get("remember", {})
    with session_scope() as s:
        for q in questions:
            key = q["key"]
            if key not in answer.get("answers", {}):
                continue
            scope = remember.get(key, "global")
            if scope == "none":
                continue
            scope_ref = {"company": ctx["company"].lower(), "job": ctx["job_id"]}.get(scope, "")
            save_answer(s, uuid.UUID(ctx["candidate_id"]), q["label"], answer["answers"][key],
                        field_type=q.get("type", "text"), options=q.get("options") or [], scope=scope,
                        scope_ref=scope_ref)


@DBOS.step()
def record_page_step(ctx: dict[str, Any], page: dict[str, Any], plan: dict[str, Any] | None,
                     fill: dict[str, Any] | None, artifacts: list[dict[str, Any]]) -> None:
    shots = [a["path"] for a in artifacts if a.get("path")]  # stored by the API when the runner reported
    with session_scope() as s:
        s.add(FormPageRecord(application_id=uuid.UUID(ctx["application_id"]), attempt=ctx["attempt"],
                             page_index=page.get("page_index", 0), url=page.get("url", ""), page=page, plan=plan,
                             fill_result=fill, screenshots=shots))


@DBOS.step()
def gate_step(ctx: dict[str, Any], plans: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    with session_scope() as s:
        cand_id = uuid.UUID(ctx["candidate_id"])
        settings = get_candidate_settings(s, cand_id)
        total, per_company = submitted_counts(s, cand_id, ctx["company"])
        d = evaluate_gate(
            plans=[FillPlan.model_validate(p) for p in plans], results=[FillResult.model_validate(r) for r in results],
            settings=settings, ats=ctx["ats"], company=ctx["company"], countries=ctx["countries"],
            remote=ctx["remote"], match_score=ctx["match_score"], legitimacy=ctx["legitimacy"],
            submitted_today=total, submitted_company_today=per_company,
            platform_native=ctx["ats"] in ("linkedin", "naukri"))
        app = s.get(Application, uuid.UUID(ctx["application_id"]))
        assert app is not None
        app.gate = d.to_json()
        return d.to_json()


@DBOS.step()
def finish_step(ctx: dict[str, Any], state: str, pages: list[dict[str, Any]], plans: list[dict[str, Any]],
                nav_labels: list[str], detail: dict[str, Any]) -> None:
    with session_scope() as s:
        app = s.get(Application, uuid.UUID(ctx["application_id"]))
        assert app is not None
        if app.state == AppState.cancelled:
            return
        if detail.get("error"):
            app.error = str(detail["error"])[:2000]
        transition(s, app, AppState(state), data=detail)
        if state in (AppState.submitted, AppState.uncertain):
            recipes.learn_from_success(s, ctx["site_key"], [FormPage.model_validate(p) for p in pages],
                                       [FillPlan.model_validate(p) for p in plans], nav_labels)
        elif state == AppState.failed:
            recipes.note_failure(s, ctx["site_key"])


@DBOS.step()
def auth_plan_step(ctx: dict[str, Any], page: dict[str, Any], tried: list[str]) -> dict[str, Any]:
    from urllib.parse import urlparse

    from sqlalchemy import select

    from jobos.db.models import SiteAccount

    kinds = {b["kind"] for b in page.get("buttons", [])}
    host = (urlparse(page.get("url", "")).hostname or "").lower()
    site_key = f"account:{host}"
    with session_scope() as s:
        cand_id = uuid.UUID(ctx["candidate_id"])
        acc = get_candidate_settings(s, cand_id).accounts
        email = acc.account_email or get_profile(s, cand_id).basics.email
        if "sso_google" in kinds and acc.use_google_sso and "google" not in tried:
            return {"method": "google", "google_account": acc.google_account}
        existing = s.scalar(select(SiteAccount).where(SiteAccount.candidate_id == cand_id,
                                                      SiteAccount.site_key == site_key))
        if existing and "login" not in tried:
            return {"method": "login", "email": existing.username, "account_ref": str(existing.id)}
        if not existing and "create" not in tried and (kinds & {"create_account", "email_signin"}) \
                and acc.account_creation != "never":
            label = "Workday" if "myworkday" in host else host
            return {"method": "create", "email": email, "site_key": site_key, "site_label": label,
                    "needs_consent": acc.account_creation == "ask"}
    return {"method": "manual"}


@DBOS.step()
def create_account_step(candidate_id: str, site_key: str, email: str) -> str:
    """Create (or reuse) a vault entry with a strong generated password. Returns the account id."""
    import secrets as pysecrets
    import string

    from sqlalchemy import select

    from jobos.db.models import AuditLog, SiteAccount
    from jobos.services.secrets import encrypt

    with session_scope() as s:
        cand_id = uuid.UUID(candidate_id)
        acct = s.scalar(select(SiteAccount).where(SiteAccount.candidate_id == cand_id, SiteAccount.site_key == site_key))
        if acct is None:
            # meets typical ATS rules: upper, lower, digit, special, length >= 8
            alphabet = string.ascii_letters + string.digits
            core = "".join(pysecrets.choice(alphabet) for _ in range(14))
            password = (pysecrets.choice(string.ascii_uppercase) + pysecrets.choice(string.ascii_lowercase)
                        + pysecrets.choice(string.digits) + pysecrets.choice("!@#$%&*") + core)
            acct = SiteAccount(candidate_id=cand_id, site_key=site_key, username=email, secret_enc=encrypt(password))
            s.add(acct)
            s.flush()
            s.add(AuditLog(actor="agent", action="account.create", target=site_key))
        return str(acct.id)


@DBOS.step()
def account_status_step(account_id: str, ok: bool) -> None:
    from jobos.db.models import SiteAccount

    with session_scope() as s:
        acct = s.get(SiteAccount, uuid.UUID(account_id))
        if acct:
            acct.status = "verified" if ok else "failed"
            if ok:
                acct.last_login_at = datetime.now(UTC)


@DBOS.step()
def allow_account_creation_step(candidate_id: str) -> None:
    with session_scope() as s:
        from jobos.services.candidates import save_candidate_settings

        st = get_candidate_settings(s, uuid.UUID(candidate_id))
        st.accounts.account_creation = "always"
        save_candidate_settings(s, uuid.UUID(candidate_id), st)


@DBOS.step()
def verification_since_step() -> str:
    return (datetime.now(UTC) - timedelta(minutes=2)).isoformat()


@DBOS.step()
def find_verification_link_step(ctx: dict[str, Any], page_url: str, since_iso: str) -> str | None:
    from urllib.parse import urlparse

    from jobos.services.verification import find_verification_link

    with session_scope() as s:
        return find_verification_link(s, get_gateway(), uuid.UUID(ctx["candidate_id"]),
                                      host=(urlparse(page_url).hostname or ""), company=ctx["company"],
                                      since=datetime.fromisoformat(since_iso))


@DBOS.step()
def set_outcome_step(app_id: str, outcome: str) -> None:
    with session_scope() as s:
        app = s.get(Application, uuid.UUID(app_id))
        if app is not None:
            app.outcome = outcome


@DBOS.step()
def file_specs_step(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    if not ctx.get("resume_document_id"):
        return []
    with session_scope() as s:
        d = s.get(Document, uuid.UUID(ctx["resume_document_id"]))
        if d is None:
            return []
        return [{"ref": str(d.id), "filename": d.filename, "download_path": f"/runner/v1/files/{d.id}"}]


# ---------------------------------------------------------------------------------- workflow --

@DBOS.workflow()
def application_workflow(app_id: str) -> str:
    ctx = start_step(app_id)
    if ctx.get("skip"):
        return f"skipped: state {ctx.get('state')}"
    DBOS.sleep(seconds_until_active_step(ctx["candidate_id"]))
    ctr = Counter()
    cid = ctx["candidate_id"]
    session = f"app:{app_id}:{ctx['attempt']}"
    files = file_specs_step(ctx)
    nav_labels: list[str] = []

    def runner(label: str, ttype: TaskType, payload: dict[str, Any], timeout_s: int = 180) -> dict[str, Any]:
        return call_runner(ctr, cid, label, ttype, session, payload, timeout_s=timeout_s)

    def fail(reason: str, state: str = AppState.failed.value) -> str:
        finish_step(ctx, state, [], [], [], {"error": reason})
        fire_runner(ctr, cid, "close", TaskType.close_session, session, {})
        return f"{state}: {reason}"

    # 1. open and reach the form ------------------------------------------------------------------
    res: dict[str, Any] = {}
    for attempt in range(3):
        res = runner(f"open-{attempt}", TaskType.open_page, {"url": ctx["apply_url"]})
        if res.get("ok") or res.get("error_kind") != "retryable":
            break
        DBOS.sleep(60 * (attempt + 1))  # durable back-off before retrying a transient failure
    if not res.get("ok"):
        if res.get("error_kind") == "not_found":
            return fail("posting page not available (HTTP 404); the employer may only accept applications on "
                        "its own careers site")
        return fail(f"could not open page: {res.get('error')}")
    record_page_step(ctx, res["data"]["page"], None, None, res.get("artifacts", []))
    page = res["data"]["page"]
    page, nav_labels, outcome = _reach_form(ctx, ctr, runner, page)
    if outcome:
        return fail(outcome, AppState.skipped.value if outcome.startswith("job closed") else AppState.failed.value)

    # 2. page loop ---------------------------------------------------------------------------------
    pages: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    extra: dict[str, Any] = {}
    for _ in range(MAX_PAGES):
        plan, fill, page_after = _complete_page(ctx, ctr, runner, page, extra, files)
        if plan is None:
            return fail(fill.get("error", "could not complete page") if fill else "expired",
                        AppState.expired.value if fill is None else AppState.failed.value)
        record_page_step(ctx, page, plan, fill, fill.get("_artifacts", []))
        fill.pop("_artifacts", None)
        pages.append(page)
        plans.append(plan)
        results.append(fill)
        buttons = {b["kind"] for b in page_after.get("buttons", [])}
        if "submit" in buttons or "next" not in buttons:
            break
        res = runner("next", TaskType.click, {"button_kind": "next"})
        if not res.get("ok"):
            return fail(f"could not go to next page: {res.get('error')}")
        page = res["data"]["page"]
        page["page_index"] = len(pages)
    else:
        return fail("too many pages")

    # 3. gate + review -----------------------------------------------------------------------------
    gate = gate_step(ctx, plans, results)
    if ctx.get("dry_run"):
        # Dry run (testing / drift canary): everything except the final click.
        finish_step(ctx, AppState.skipped.value, pages, plans, nav_labels,
                    {"dry_run": True, "gate": gate, "outcome": "dry_run_complete"})
        set_outcome_step(app_id, "dry_run_complete")
        fire_runner(ctr, cid, "close", TaskType.close_session, session, {})
        return "dry_run_complete"
    if not gate["ok"]:
        return fail("submit gate blocked: " + "; ".join(gate["problems"][:5]))
    if gate["action"] != "auto_submit":
        set_state_step(app_id, AppState.ready_for_review.value, {"rule": gate["rule"]})
        decision = ask_human(ctr, cid, app_id, "review_before_submit",
                             f"Review: {ctx['title']} at {ctx['company']}",
                             {"job": _job(ctx), "gate": gate, "match_score": ctx["match_score"],
                              "pages": _review_pages(pages, plans)})
        if decision is None:
            return fail("review expired", AppState.expired.value)
        if decision.get("decision") != "approve":
            return fail("skipped by you during review", AppState.skipped.value)
        set_state_step(app_id, AppState.in_progress.value, {"approved_via": "review"})

        # the tab may have been closed while waiting: replay deterministically from stored plans
        check = runner("check-alive", TaskType.extract, {})
        if not check.get("ok") or check["data"]["page"].get("kind") != "form":
            replay = _replay(ctx, runner, pages, plans, files)
            if replay:
                return fail(replay)

    # 4. submit ------------------------------------------------------------------------------------
    set_state_step(app_id, AppState.submitting.value)
    res = runner("submit", TaskType.submit, {"gate_token": gate_token(app_id, ctx["attempt"])}, timeout_s=120)
    sub = SubmitResult.model_validate(res["data"]["result"]) if res.get("ok") else None
    if sub and sub.page:
        record_page_step(ctx, sub.page.model_dump(mode="json"), None, None, res.get("artifacts", []))
    if sub is None:
        state, detail = AppState.uncertain.value, {"error": res.get("error", "submit failed")}
    elif sub.confirmed:
        state, detail = AppState.submitted.value, {"confirmation": sub.confirmation_text[:500], "url": sub.final_url}
    elif sub.submitted:
        state, detail = AppState.uncertain.value, {"note": "no confirmation page detected", "url": sub.final_url}
    elif sub.page and sub.page.kind == PageKind.captcha:
        # Real browser rarely sees this; a human solves it, then we check the result.
        ans = ask_human(ctr, cid, app_id, "captcha", f"CAPTCHA on {ctx['company']} application",
                        {"job": _job(ctx), "message": "Solve the CAPTCHA in the JobOS Chrome window (it will submit), then tap Done."})
        after = runner("after-captcha", TaskType.extract, {}) if ans else {"ok": False}
        confirmed = after.get("ok") and after["data"]["page"].get("kind") == "confirmation"
        state = AppState.submitted.value if confirmed else AppState.uncertain.value
        detail = {"note": "captcha solved by user" if ans else "captcha not solved"}
    elif sub.page and sub.page.kind == PageKind.form and sub.page.errors:
        # The site's own validation rejected the click and the form is still on screen: nothing was sent,
        # so this is a retryable failure, not an "uncertain" submission.
        state, detail = AppState.failed.value, {"note": "form validation blocked submit (not sent)",
                                                "errors": sub.page.errors[:5], "url": sub.final_url}
    else:
        errors = sub.page.errors if sub.page else []
        state, detail = AppState.uncertain.value, {"note": "submit did not complete", "errors": errors[:5]}
    finish_step(ctx, state, pages, plans, nav_labels, detail)
    fire_runner(ctr, cid, "close", TaskType.close_session, session, {})
    return state


# ---------------------------------------------------------------------------- sub-procedures --

def _job(ctx: dict[str, Any]) -> dict[str, Any]:
    return {"title": ctx["title"], "company": ctx["company"], "url": ctx["apply_url"], "id": ctx["job_id"]}


def _reach_form(ctx, ctr, runner, page) -> tuple[dict[str, Any], list[str], str]:
    """Get from whatever page we landed on to the application form."""
    nav_labels: list[str] = []
    auth_tried: list[str] = []
    recipe_nav = list(ctx.get("recipe_nav") or [])
    for _step in range(MAX_NAV_STEPS):
        kind = page.get("kind")
        if kind == "form":
            return page, nav_labels, ""
        if kind == "closed":
            return page, nav_labels, "job closed / no longer accepting applications"
        if kind == "login" and len(auth_tried) < 4:
            page, done_note = _authenticate(ctx, ctr, runner, page, auth_tried)
            if done_note == "dry_run_stop":
                return page, nav_labels, "dry run stopped at account creation (no account was created)"
            continue
        if kind in ("login", "captcha"):
            ans = ask_human(ctr, ctx["candidate_id"], ctx["application_id"],
                            "login_required" if kind == "login" else "captcha",
                            f"{'Log in' if kind == 'login' else 'CAPTCHA'} needed for {ctx['company']}",
                            {"job": _job(ctx), "url": page.get("url"),
                             "message": "Complete this in the JobOS Chrome window on your computer, then tap Done."})
            if ans is None:
                return page, nav_labels, "login/captcha not completed"
            res = runner("re-extract", TaskType.extract, {})
            if not res.get("ok"):
                return page, nav_labels, res.get("error", "extract failed")
            page = res["data"]["page"]
            continue
        if any(b["kind"] == "apply" for b in page.get("buttons", [])):
            res = runner("apply-click", TaskType.click, {"button_kind": "apply"})
            if not res.get("ok"):
                return page, nav_labels, f"apply button failed: {res.get('error')}"
            page = res["data"]["page"]
            nav_labels.append("apply")
            continue
        # unknown page: Navigator agent (recipe first, then LLM)
        obs = runner("observe", TaskType.observe, {})
        if not obs.get("ok"):
            return page, nav_labels, obs.get("error", "observe failed")
        action = decide_nav_step(ctx, obs["data"]["observation"], recipe_nav, nav_labels)
        if action["kind"] in ("fail", "done"):
            return page, nav_labels, f"could not find the application form ({action.get('reason', '')})"
        label = action.pop("label", "")
        res = runner("act", TaskType.act, {"action": action, "allowed_hosts": _allowed_hosts(ctx, page)})
        if not res.get("ok"):
            return page, nav_labels, f"navigation failed: {res.get('error')}"
        page = res["data"]["page"]
        if label:
            nav_labels.append(label)
    return page, nav_labels, "could not reach the application form"


def _authenticate(ctx, ctr, runner, page, tried: list[str]) -> tuple[dict[str, Any], str]:
    """Sign-in wall: Google SSO → saved vault account → create account (per settings) → manual fallback."""
    plan = auth_plan_step(ctx, page, tried)
    method = plan["method"]
    tried.append(method)
    if method == "manual":
        ans = ask_human(ctr, ctx["candidate_id"], ctx["application_id"], "login_required",
                        f"Sign-in needed for {ctx['company']}",
                        {"job": _job(ctx), "url": page.get("url"),
                         "message": "Sign in (or create the account) in the JobOS Chrome window, then tap Done."})
        tried.extend(["google", "login", "create"])
        if ans is None:
            return page, "login not completed"
        res = runner("re-extract-auth", TaskType.extract, {})
        return (res["data"]["page"] if res.get("ok") else page), ""
    if method == "create":
        if ctx.get("dry_run"):
            return page, "dry_run_stop"
        if plan.get("needs_consent"):
            ans = ask_human(ctr, ctx["candidate_id"], ctx["application_id"], "account_creation_consent",
                            f"Create a {plan['site_label']} account for {ctx['company']}?",
                            {"job": _job(ctx), "url": page.get("url"), "email": plan["email"],
                             "message": f"{ctx['company']} requires an account. JobOS will create one with "
                                        f"{plan['email']} and a strong generated password stored in your vault."})
            if ans is None or ans.get("decision") not in ("approve", "always"):
                tried.extend(["create"])
                return page, "account creation declined"
            if ans.get("decision") == "always":
                allow_account_creation_step(ctx["candidate_id"])
        plan["account_ref"] = create_account_step(ctx["candidate_id"], plan["site_key"], plan["email"])
    res = runner(f"auth-{method}", TaskType.auth, {"method": method, "email": plan.get("email", ""),
                                                   "account_ref": plan.get("account_ref", ""),
                                                   "google_account": plan.get("google_account", "")}, timeout_s=240)
    if not res.get("ok"):
        return page, f"auth failed: {res.get('error')}"
    new_page = res["data"]["page"]
    if res["data"].get("verify_email"):
        # 1) try the inbox: open the employer's verification link in a side tab, then come back
        since = verification_since_step()
        for _ in range(10):  # ~5 minutes
            link = find_verification_link_step(ctx, new_page.get("url", ""), since)
            if link:
                side = runner("verify-open", TaskType.open_page, {"url": link}, timeout_s=120)
                if side.get("ok"):
                    r2 = runner("after-verify", TaskType.open_page, {"url": ctx["apply_url"]})
                    if r2.get("ok"):
                        return r2["data"]["page"], ""
                break
            DBOS.sleep(30)
        # 2) fall back to the human
        ans = ask_human(ctr, ctx["candidate_id"], ctx["application_id"], "verify_email",
                        f"Verify your email for {ctx['company']}",
                        {"job": _job(ctx), "email": plan.get("email", ""),
                         "message": "Open the verification email from the employer's careers site and click the "
                                    "link (or let JobOS read it from your inbox), then tap Done."})
        if ans is not None:
            r2 = runner("re-extract-verify", TaskType.extract, {})
            new_page = r2["data"]["page"] if r2.get("ok") else new_page
    if plan.get("account_ref"):
        account_status_step(plan["account_ref"], new_page.get("kind") != "login")
    return new_page, ""


def _allowed_hosts(ctx: dict[str, Any], page: dict[str, Any]) -> list[str]:
    from urllib.parse import urlparse

    hosts = {urlparse(ctx["apply_url"]).hostname or "", urlparse(page.get("url", "")).hostname or ""}
    hosts |= {"greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com", "smartrecruiters.com",
              "icims.com", "workable.com", "accounts.google.com"}
    return sorted(h for h in hosts if h)


def _complete_page(ctx, ctr, runner, page, extra, files):
    """Resolve → ask the human for gaps → fill → verify (retry once with site errors)."""
    error_hints: dict[str, str] = {}
    fill: dict[str, Any] = {}
    plan: dict[str, Any] = {}
    page_after = page
    for attempt in range(3):
        plan = resolve_step(ctx, page, extra, error_hints)
        unresolved = [u for u in plan["unresolved"] if u.get("required", True)]
        if unresolved:
            set_state_step(ctx["application_id"], AppState.needs_input.value)
            questions = [{"key": u["key"], "label": u["label"], "type": u["type"], "options": u.get("options", []),
                          "reason": u.get("reason", ""), "suggestion": u.get("suggestion")} for u in unresolved]
            ans = ask_human(ctr, ctx["candidate_id"], ctx["application_id"], "missing_answer",
                            f"{len(questions)} question(s) for {ctx['company']}",
                            {"job": _job(ctx), "questions": questions})
            if ans is None:
                return None, None, page
            save_answers_step(ctx, questions, ans)
            extra.update(ans.get("answers", {}))
            set_state_step(ctx["application_id"], AppState.in_progress.value)
            plan = resolve_step(ctx, page, extra, error_hints)
            if any(u.get("required", True) for u in plan["unresolved"]):
                continue
        res = runner(f"fill-p{page.get('page_index', 0)}", TaskType.fill, {"plan": plan, "files": files},
                     timeout_s=600)
        if not res.get("ok"):
            return None, {"error": f"fill failed: {res.get('error')}"}, page
        fill = res["data"]["result"]
        fill["_artifacts"] = res.get("artifacts", [])
        page_after = fill.get("page") or page
        bad = {r["key"]: r.get("error", "") for r in fill["results"] if not r["ok"]}
        page_errors = (fill.get("page") or {}).get("errors", [])
        if not bad and not page_errors:
            return plan, fill, page_after
        if attempt == 2:
            break
        # re-resolve failing fields with the site's feedback; extra keys force a fresh answer
        error_hints = {k: (v or "; ".join(page_errors)) for k, v in bad.items()} or {
            f["key"]: "; ".join(page_errors) for f in (fill.get("page") or {}).get("fields", [])
            if f.get("required") and not f.get("current_value")}
        page = page_after
    return plan, fill, page_after


def _replay(ctx, runner, pages, plans, files) -> str:
    res = runner("replay-open", TaskType.open_page, {"url": ctx["apply_url"]})
    if not res.get("ok"):
        return f"replay open failed: {res.get('error')}"
    if res["data"]["page"].get("kind") == "job_description":
        res = runner("replay-apply", TaskType.click, {"button_kind": "apply"})
    for i, plan in enumerate(plans):
        r = runner(f"replay-fill-{i}", TaskType.fill, {"plan": plan, "files": files}, timeout_s=600)
        if not r.get("ok") or any(not x["ok"] for x in r["data"]["result"]["results"]):
            return "replay after review did not reproduce the form; please re-run"
        if i < len(plans) - 1:
            r = runner(f"replay-next-{i}", TaskType.click, {"button_kind": "next"})
            if not r.get("ok"):
                return "replay could not advance pages"
    return ""


def _review_pages(pages: list[dict[str, Any]], plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for page, plan in zip(pages, plans, strict=False):
        labels = {f["key"]: f["label"] for f in page.get("fields", [])}
        out.append({"url": page.get("url"), "fields": [
            {"label": labels.get(v["key"], v["key"]), "value": v.get("value") if v.get("value") is not None else
             ("(file)" if v.get("file_ref") else None), "source": v["source"], "confidence": v.get("confidence")}
            for v in plan["values"]]})
    return out


def enqueue_application(app_id: str, company: str, workflow_id: str) -> None:
    """Enqueue on the apply queue, partitioned per company (one at a time per employer)."""
    from dbos import SetEnqueueOptions, SetWorkflowID

    from .runtime import APPLY_QUEUE

    apply_queue = DBOS.retrieve_queue(APPLY_QUEUE)
    assert apply_queue is not None
    with SetWorkflowID(workflow_id), \
            SetEnqueueOptions(queue_partition_key=company.lower() or "default"):
        apply_queue.enqueue(application_workflow, app_id)

