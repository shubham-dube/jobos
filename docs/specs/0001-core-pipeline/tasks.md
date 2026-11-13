# Tasks 0001: Core pipeline

- [x] Workspace scaffold (uv + pnpm), Postgres schema + Alembic, CI
- [x] LLM gateway: providers (OpenRouter, fake), per-task routing, structured output repair, ledger, budget
- [x] Sources: Greenhouse/Lever/Ashby + seed list; normalize, dedup, close detection
- [x] Matching: filters, seniority, eligibility (visa/remote restrictions), legitimacy, LLM fit score, prescore ordering
- [x] Runner: persistent Chrome profile, extractor JS, option harvesting, human-like fill, verify, submit, navigator
- [x] Server brain: taxonomy, answer bank, resolver (+ re-ask, option trimming), gate + approval rules, recipes
- [x] DBOS workflows: application (pages loop, interventions, review, replay, submit), discovery (crawl, evaluate,
      auto-queue), inbox, schedules, partitioned apply queue (one per employer at a time)
- [x] API: dashboard, runner protocol, WhatsApp webhook; CLI
- [x] Notifications (WhatsApp, Resend), IMAP inbox clerk
- [x] Dashboard (Next.js)
- [x] Tests: 30 (unit + e2e real browser vs fake multi-page ATS); live dry runs on Greenhouse + Lever
- [ ] Founder acceptance (AC11)
- [ ] Next: JobSpy connector (LinkedIn/Indeed/Naukri discovery), Workday adapter + vault, tailoring (RenderCV)
