# ADR-0016: Sign-in walls — Google SSO first, vault accounts, consented account creation

- Status: Accepted
- Date: 2026-11-13
- Related: ADR-0004, ADR-0008, FR-ACC-1..3, security-and-privacy.md

## Context
Workday (and many career sites) require an account per employer before applying. The founder wants everything
automatic. Live exploration of NVIDIA's Workday showed "Sign in with Google", "Sign in with LinkedIn" and
"Sign in with email" (→ create account) on the first step of the apply flow.

## Decision
Order of attempts when the runner lands on a sign-in wall (page kind `login`):
1. **Google SSO** (default on): click "Sign in with Google", pick the configured Google account in the chooser
   (the runner's dedicated Chrome profile is logged into Google once by the founder). No password involved.
2. **Saved vault account** for that site (`site_accounts`, password encrypted).
3. **Create an account** with the configured email and a generated strong password, governed by
   `settings.accounts.account_creation`: `ask` (default; one-tap consent with "Always allow"), `always`, `never`.
   Dry runs never create accounts.
4. **Manual**: intervention asking the founder to sign in in the runner's window.
If the site then asks to verify the email address, a `verify_email` intervention is raised (inbox automation
for verification links is the next step).

Passwords never appear in DBOS workflow history, task payloads or logs: tasks carry an `account_ref`; the runner
fetches the secret just-in-time from `GET /runner/v1/secrets/{id}` (runner-token authenticated, candidate-scoped,
audited in `audit_log`). The LLM never sees or types credentials; the Navigator cannot type into password fields.

## Consequences
+ Most Workday tenants become fully automatic after one Google login on the runner.
− Each created account is an outward action under the founder's identity → consent by default, audit trail.
