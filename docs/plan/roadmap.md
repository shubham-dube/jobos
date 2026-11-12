# Roadmap

Status: In review. Durations are rough estimates for founder + Claude working steadily; they will be re-estimated after Phase 0.

## Phase 0 — Foundations (≈ 1 week)
**Goal:** decisions made; repo, tooling and CI ready, so every later PR is small and safe.
- Founder reviews docs and answers DECISIONS-NEEDED.
- Repo scaffolding: uv + pnpm workspaces, justfile, Compose (Postgres, Temporal dev, MinIO), pre-commit, CI skeleton, PR/issue templates, branch protection, Renovate.
- Skeleton apps: API health endpoint, worker hello-workflow, web shell with auth stub, runner that pairs and opens Chrome.
- **Exit:** `just dev` runs the stack; CI green; a trivial workflow runs end to end through the runner.

## Phase 1 — Founder MVP ("it applies for me") (≈ 4–6 weeks)
**Goal:** founder's search runs daily on Greenhouse/Lever/Ashby jobs with review-before-submit.
- Master profile import + editor; documents; presets (FR-PROF-1..4).
- Answer bank + interventions + Telegram bot (FR-ANS-1..3, FR-HITL-1..5).
- Discovery: Greenhouse/Lever/Ashby APIs, JobSpy read-only, job-alert email parsing, paste-a-URL (FR-DISC-1,2,3,5, FR-MAIL-3).
- Verification v1 + match scoring v1 (FR-VER-1,2, FR-MATCH-1,2).
- Form engine + adapters: Greenhouse, Lever, Ashby; submit gate; evidence bundle (FR-APP-1,5,6,7).
- Local runner with dedicated Chrome profile; session health (FR-ACC-1).
- Dashboard v1: feed, pipeline, intervention inbox, application detail, profile/answers, connections (FR-DASH-1).
- Observability baseline (traces, Langfuse, Sentry); cost per application measured.
- **Exit:** 2 consecutive weeks of daily use; ≥ 50 applications submitted; 0 wrong submissions; autonomy rate measured; founder time < 15 min/day.

## Phase 2 — Robust autopilot (≈ 4–6 weeks)
**Goal:** covers most of the founder's target jobs, self-tracking, fewer interventions.
- Workday adapter incl. per-tenant account creation + vault; SmartRecruiters, iCIMS, Workable; Google Forms, Microsoft Forms (FR-APP-2, FR-ACC-2).
- Generic engine fallback + Navigator agent with restricted tools (FR-APP-3).
- Inbox tracking (Gmail API for founder), status automation, OTP/verify-link handling (FR-MAIL-1,2, FR-ACC-3).
- Ghost-job signals, more sources (FR-VER-3, FR-DISC-4).
- Resume tailoring + cover letters with grounding (FR-TAIL-1,2).
- Opt-in platform-native apply (Naukri / LinkedIn Easy Apply) if founder chooses (FR-APP-4).
- Drift canaries nightly; analytics v1 (FR-DASH-2).
- Runner desktop packaging (tray app, auto-update).
- **Exit:** autonomy rate ≥ 60%; adapter success targets met; inbox auto-updates ≥ 90% of statuses.

## Phase 3 — Product beta (≈ 6–8 weeks)
**Goal:** 20–100 external users paying or on waitlist-to-paid.
- Multi-tenant auth (Clerk or chosen), onboarding flow, billing (Stripe/Razorpay), usage metering (FR-PLAT-1,3).
- Cloud runner tier (managed or Steel self-host) with live view and sticky proxies (FR-PLAT-2, FR-HITL-4).
- Email forwarding path for public users (ADR-0007).
- Chrome extension "assist mode" (autofill any form from answer bank, verifier badge).
- Interview prep pack, resume A/B analytics.
- Security hardening: pen test, privacy policy/ToS, data export/delete (FR-PLAT-4), backups/DR.
- **Exit:** beta users retained 4+ weeks; NPS > 40; 0 account bans; unit economics measured.

## Phase 4+ — Growth
Free verifier tool, referral copilot, agency mode (B2B), hiring signals, visa filter, WhatsApp, generalized form agent.
