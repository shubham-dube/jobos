# Browser execution — runners, real browsers, logins

Status: In review — core decision is DECISIONS-NEEDED Q3 / ADR-0004

## 1. Requirements (from the founder)
- Apply from a **real browser** where the user's email/Google account is logged in.
- Keep accounts logged in "all the time"; when manual login is needed, the user does it.
- Work for both common portals and sign-in-required portals.
- Must work later as a **product** for many users.

## 2. Options considered

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. Local runner (dedicated Chrome profile)** | A small app on the user's computer launches the user's installed Google Chrome with a *dedicated, persistent* profile directory via Playwright `launch_persistent_context(channel="chrome")`. User logs into Google/LinkedIn/etc. once in that window. | Real device fingerprint + home IP → lowest ban/CAPTCHA risk; sessions stay on user's machine (privacy); zero browser/proxy cost; fastest to build | Computer must be on; desktop packaging/updates; varied OSes |
| B. Attach to user's everyday Chrome profile via CDP | Remote-debug the user's main profile | Already logged in everywhere | Recent Chrome versions block remote debugging on the default profile for security; fragile; risky to touch user's main browser — **rejected** |
| **C. Browser extension in the user's main Chrome** | MV3 extension fills forms in the user's real tabs; control plane sends tasks | Truly "my real browser"; great for manual-assist autofill and Google Forms | MV3 service-worker limits; hard to run long unattended flows; store review — **good complement (P3), not the core executor** |
| **D. Cloud runner** | Containerized Chrome per user with persistent encrypted profile, sticky residential/ISP proxy in user's region, live view for logins | Works 24/7 without user's laptop; scalable product tier | Higher cost; higher bot-detection risk; we hold session cookies (security burden) |
| E. Managed cloud browsers (Browserbase, Steel Cloud, Kernel, Hyperbrowser) | Same as D, bought | Faster to ship D; profiles, live view, proxies built in | Vendor cost/lock-in; sessions at a third party |

## 3. Recommendation
**A now (P1–P2), add D/E as a paid tier in P3, add C as the "assist" extension in P3.** All share one **Runner Protocol**, so the workflow code doesn't care where the browser is.

## 4. Runner Protocol (v0 sketch)

- Runner authenticates with a device token (issued when the user pairs the runner from the dashboard; revocable).
- Runner keeps an **outbound** WebSocket (fallback: HTTPS long-poll) to the API. No inbound ports on the user's machine.
- Messages (JSON, versioned):
  - `runner.hello {runner_id, version, capabilities, browser_version, os}`
  - `task.assign {task_id, type, payload, deadline}` — types: `session.check`, `session.login_assist`, `form.extract`, `form.fill_page`, `form.submit`, `page.capture`, `nav.step` (fallback agent)
  - `task.progress {task_id, step, screenshot_ref?, log}`
  - `task.result {task_id, status, data, artifacts[]}`
  - `task.cancel {task_id}`
  - `heartbeat`
- Artifacts (screenshots, DOM snapshots) uploaded directly to object storage via pre-signed URLs.
- The worker side wraps these as Temporal activities with heartbeats; if the runner disconnects, the activity times out and the workflow retries or pauses.

## 5. Sessions & logins

- **One dedicated browser profile per candidate per runner** (`~/.jobos/profiles/<candidate_id>/`). The user logs into Google first — many ATSs offer "Sign in with Google", and Google sign-in in this profile then covers them.
- `SessionHealthWorkflow` checks known sites by visiting a lightweight authenticated URL and looking for logged-in markers; results shown on the Connections page.
- When logged out: `LOGIN_REQUIRED` intervention → local runner brings the window to front at the login page; cloud runner offers live view.
- **Per-employer accounts (Workday etc.):** with consent (`ACCOUNT_CREATION_CONSENT`, can be "always allow"), the adapter creates the account using the candidate's email and a generated strong password stored in the vault; email verification link/OTP is read via inbox integration (scoped to the active attempt).
- MFA codes: user types them (or forwards SMS manually); we never automate SMS interception in P1–P3.

## 6. Human-like behavior & platform safety
- Real Chrome (not Chromium-for-testing) on local runner; no stealth hacks needed because it *is* a normal browser on a normal machine.
- Typing with small randomized delays; scroll before click; no parallel tabs on the same site.
- Caps and pacing from policy (agents-and-workflows §6).
- **We do not evade bot detection** beyond behaving like one human using a normal browser. If a site blocks, we stop and ask.

## 7. Local runner packaging plan
- P1: `uv run jobos-runner` CLI for the founder (macOS/Windows/Linux).
- P2: signed desktop app (Tauri shell around the Python runner, or PyInstaller bundle) with tray icon, auto-update, pairing via QR/code, "pause all" switch.
- Runner self-update channel and version compatibility checks in `runner.hello`.

## 8. Cloud runner plan (P3)
- Container image: Chrome + runner; one container per active task; profile blob (encrypted with per-user key) mounted/restored at start and saved at end.
- Sticky proxy per candidate in their country (static ISP/residential) so sessions don't flip IPs.
- Live view via CDP screencast streamed to dashboard for takeovers.
- Build on Steel browser (Apache-2.0) self-hosted **or** a managed provider — decide in P3 with a cost/reliability spike.
