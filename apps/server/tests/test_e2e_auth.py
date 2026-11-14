"""Sign-in walls: Google SSO popup and Workday-style account creation with the vault (fake site)."""

from __future__ import annotations

import pytest

from .test_e2e_apply import resolve_handler

pytestmark = pytest.mark.browser


def _set_accounts(st, **kw) -> None:
    s = st.api.get("/api/v1/settings").json()
    s["accounts"].update(kw)
    st.api.put("/api/v1/settings", json=s).raise_for_status()


def _finish_review(st, app_id: str) -> None:
    def step():
        iv = st.open_iv("missing_answer", app_id)
        if iv:  # salary may already be in the answer bank from another test
            st.api.post(f"/api/v1/interventions/{iv['id']}/answer",
                        json={"answers": {q["key"]: "80000" for q in iv["payload"]["questions"]}}).raise_for_status()
            return None
        return st.open_iv("review_before_submit", app_id)

    iv = st.wait(step, app_id, timeout=180)
    st.api.post(f"/api/v1/interventions/{iv['id']}/answer", json={"decision": "approve"}).raise_for_status()
    st.wait(lambda: st.api.get(f"/api/v1/applications/{app_id}").json()["state"] == "submitted", app_id)


def test_google_sso_sign_in(e2e_stack) -> None:
    st = e2e_stack
    st.fake.on("form.resolve", resolve_handler)
    _set_accounts(st, use_google_sso=True, google_account="aarav.mehta@example.com", account_creation="ask")
    app_id = st.api.post(f"/api/v1/jobs/{st.add_job('wd_job.html', 'Software Engineer', 'SSO Corp')}/apply").json()[
        "application_id"]
    _finish_review(st, app_id)
    events = st.api.get(f"/api/v1/applications/{app_id}").json()["events"]
    assert not any(e["to"] == "needs_input" and "login" in str(e["data"]) for e in events)


def test_account_creation_with_consent_and_vault(e2e_stack) -> None:
    from sqlalchemy import select

    from jobos.db import session_scope
    from jobos.db.models import AuditLog, SiteAccount
    from jobos.services.secrets import decrypt

    st = e2e_stack
    st.fake.on("form.resolve", resolve_handler)
    _set_accounts(st, use_google_sso=False, account_creation="ask")
    app_id = st.api.post(f"/api/v1/jobs/{st.add_job('wd_job.html', 'Backend Engineer II', 'Vault Corp')}/apply").json()[
        "application_id"]
    iv = st.wait(lambda: st.open_iv("account_creation_consent", app_id), app_id)
    assert iv["payload"]["email"] == "aarav.mehta@example.com"
    st.api.post(f"/api/v1/interventions/{iv['id']}/answer", json={"decision": "always"}).raise_for_status()
    _finish_review(st, app_id)
    with session_scope() as s:
        acct = s.scalar(select(SiteAccount).where(SiteAccount.site_key == "account:127.0.0.1"))
        assert acct is not None and acct.status == "verified"
        pw = decrypt(acct.secret_enc)
        assert len(pw) >= 16 and any(ch.isupper() for ch in pw) and any(ch.isdigit() for ch in pw)
        assert s.scalar(select(AuditLog).where(AuditLog.action == "vault.read"))
    assert st.api.get("/api/v1/settings").json()["accounts"]["account_creation"] == "always"
