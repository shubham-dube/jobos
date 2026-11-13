# Decisions needed from the founder

Status: Decided (2026-11-13) — see log at bottom. Original questions kept for history.

**Answer these before Phase 1 starts.** For each one: pick an option (or write your own) and add notes. My recommendation is marked ⭐. When a decision is made I'll update the related ADR to `Accepted` and move the item to the "Decided" log at the bottom.

---

### Q1. Scope and sequencing
Do you agree with the phase plan in [plan/roadmap.md](plan/roadmap.md) and the picks in [product/opportunity-map.md](product/opportunity-map.md)?
- ⭐ A. Yes: Phase 1 = core autopilot on Greenhouse/Lever/Ashby + answer bank + interventions + Telegram; Workday/inbox/tailoring in Phase 2.
- B. Move something earlier (say which — e.g. Workday or Naukri in Phase 1).
- C. Other.

### Q2. Target market and roles (affects sources, adapters, currency, legal)
- Where are *you* job hunting? Which countries/cities/remote? Which roles and seniority?
- First external market for the product:
  - ⭐ A. India first (Naukri ecosystem, Google Forms, Darwinbox/Keka ATSs, INR pricing, DPDP), with global-remote jobs on Greenhouse/Lever/Ashby included from day 1.
  - B. US first (Workday-heavy, H-1B/visa angle, USD pricing).
  - C. Global remote tech only.

### Q3. Where the browser runs (ADR-0004)
- ⭐ A. Local-first: a runner on your computer drives a dedicated, persistent Chrome profile where you log in once (Google, LinkedIn, Naukri…). Cloud runner later as a paid tier.
- B. Cloud-first (24/7 without your laptop; higher cost and ban risk; we hold session cookies).
- Also: which OS is your main machine (macOS / Windows / Linux)? Is it OK to keep it on during your chosen "active hours"?

### Q4. LinkedIn / Naukri / Indeed automation (ADR-0006)
- ⭐ A. Apply on employer ATS by default; platform-native apply (Easy Apply / Naukri) off by default, opt-in later with low caps; never automate messaging.
- B. Include Naukri apply in Phase 1 for you (accept the account risk).
- C. Include LinkedIn Easy Apply in Phase 1 (highest risk).

### Q5. Default submit mode
- ⭐ A. `always_review` for your first ~30 applications (you approve each from phone/dashboard in seconds), then switch to `auto_if_confident`.
- B. `auto_if_confident` from day 1.
- C. Always review, forever.

### Q6. Email integration (ADR-0007)
- Which email do you use for job applications (Gmail / Google Workspace / Outlook / other)?
- ⭐ A. Phase 1–2: Gmail API with your own Google Cloud project in testing mode (only you). Public beta: forwarding by default, IMAP optional. Gmail API publicly + CASA assessment once revenue justifies.
- B. Forwarding only, even for you.
- C. Go for Gmail API verification + CASA early.

### Q7. Hosting, region, budget
- ⭐ A. Phase 0–2: everything runs on your machine via Docker Compose (+ optional small VM for always-on discovery). Phase 3: AWS (Mumbai region if India-first) with Temporal Cloud, managed Postgres, S3, KMS, IaC.
- B. Simpler PaaS (Fly.io/Railway + Neon + R2) for Phase 3, migrate later if needed.
- C. GCP / Azure (if you have credits — tell me).
- Monthly budget you're comfortable with during Phase 1–2 for LLM API + infra? (e.g. $50 / $150 / $300)

### Q8. Authentication provider (Phase 3, but affects data model now)
- ⭐ A. Clerk (Google sign-in, MFA, organizations for agency mode; fastest).
- B. Self-hosted (Better Auth / Auth.js) — no vendor cost, more work.
- C. Supabase Auth.

### Q9. LLM models and API key
- Default for all agents: `claude-opus-5-5` (best quality; ~$4/$20 per million input/output tokens).
- ⭐ A. Start everything on Opus 5.5; allow switching specific high-volume routes (e.g. email classification, match pre-screening) to `claude-sonnet-5-5` or `claude-haiku-5-5` **only when evals show no quality loss and you approve each switch**.
- B. Opus 5.5 everywhere, no routing.
- C. Cheapest viable models from the start.
- Whose Anthropic API key in Phase 1? (You create one at console.anthropic.com and put it in your local `.env`; for the cloud session I don't need it unless we run live evals.)

### Q10. Notifications / phone channel for interventions
- ⭐ A. Telegram bot (instant, free, buttons for one-tap answers) + web push.
- B. WhatsApp (needs Business API approval and per-message cost) — later.
- C. Email only.

### Q11. Name, repo, openness
- Working name "JobOS" is a placeholder (not trademark-checked). Do you have a name in mind?
- ⭐ Repo: **private** GitHub repo (see "What repo to create" in the chat/README).
- Open-source strategy: ⭐ A. closed source for now (keeps options open); B. open-core later (runner + adapters open, cloud closed); C. fully open.

### Q12. Your own data for dogfooding
When Phase 1 starts I'll need: your latest resume(s), target roles/locations/salary, work authorization, notice period, links (LinkedIn/GitHub/portfolio), and standard answers. Where do you want this stored?
- ⭐ A. Only on your machine (local DB/runner); never committed to git; test fixtures use a fake persona.
- B. Also in a private staging environment.

### Q13. Anything I missed?
Features, constraints, deadlines (e.g. "I need interviews by <date>"), team members, existing accounts/credits.

---

## Decided log
| Date | Q | Decision | ADR updated |
|---|---|---|---|
| 2026-11-13 | Q1 | Roadmap OK. Orchestrated multi-agent system; agents may use the browser for anything without an API (incl. reading webmail). Agents learn **site recipes** automatically for recurring sites (not one-off sites). Target **high volume** (thousands of applications), human-like. | ADR-0014, agents-and-workflows.md |
| 2026-11-13 | Q2 | Founder in India; open to India + abroad (CH, UK, US, AU, NZ, anywhere) + remote; prefer top-quality employers; sponsorship/eligibility for an Indian citizen must be evaluated per job. | matching rules |
| 2026-11-13 | Q3 | Local-first runner on **Windows**; cloud later. | ADR-0004 Accepted |
| 2026-11-13 | Q4 | Everything automatic; behave like a human. Platform-native apply allowed (opt-in per platform, caps). | ADR-0006 Accepted (amended) |
| 2026-11-13 | Q5 | Everything in review at first; founder-configurable **auto-approval rules** decide what auto-submits. | ADR-0015 |
| 2026-11-13 | Q6 | Gmail + Zoho Mail, for founder use. IMAP (app passwords) first, browser fallback, Gmail API later. Public launch of any piece only if compliant. | ADR-0007 Accepted (amended) |
| 2026-11-13 | Q7 | A (local first; AWS later). | — |
| 2026-11-13 | Q8 | Delegated to Claude: staged auth — single-owner token auth now, Clerk at Phase 3. | ADR-0013 |
| 2026-11-13 | Q9 | Multi-provider LLM layer; **OpenRouter** first, Gemini later; per-task model routing; tests on cheap models ($5 budget). | ADR-0011 |
| 2026-11-13 | Q10 | **WhatsApp** + **email via Resend** (domain configured). | ADR-0012 |
| 2026-11-13 | Q11 | Open repository for now. ⇒ never commit personal data. | — |
| 2026-11-13 | Q12 | Personal data local only; commit fake profiles only. | — |
| 2026-11-13 | — | Durable workflows: **DBOS (Postgres-only)** replaces Temporal. | ADR-0010 supersedes ADR-0003 |
