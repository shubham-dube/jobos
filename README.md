# JobOS (working name)

> An autopilot for the job search: agents that **find** real jobs that fit you, **verify** they are legitimate, **apply** through a real browser using your own logged-in accounts, **track** every reply in your inbox, and **stop and ask you** whenever they are missing information.

Status: **Phase 1 — founder MVP working end to end** (see [spec 0001](docs/specs/0001-core-pipeline/spec.md)).
Run it on your machine: [`docs/engineering/runbook-local.md`](docs/engineering/runbook-local.md).

**What works today:** discovery across 111+ employer job boards (Greenhouse, Lever, Ashby) with visa/eligibility
checks for your citizenship, legitimacy scoring and AI fit scores · applying through your own Chrome via a local
runner (generic form engine, verified on live Greenhouse and Lever forms) · asks you only what it can't prove from
your profile, and remembers the answer · review-by-default with your own auto-approval rules · durable workflows
(DBOS on Postgres) · evidence for every application · Gmail/Zoho tracking via IMAP · WhatsApp + email notifications ·
Next.js dashboard.

## Why this exists

Job hunting is a funnel with too much manual, repetitive work: searching ten portals, filtering out stale or fake postings, retyping the same answers into hundreds of forms, creating a new Workday account for every employer, and losing track of who replied. Existing "auto-apply" tools mostly spray low-quality applications from a cloud bot, get users' accounts restricted, and do not tell you what they actually submitted.

JobOS takes the opposite position: **fewer, better, verified applications**, submitted from **your real browser**, with a **complete record** of every answer sent, and a human in the loop exactly where it matters.

## Where to read next

| If you want to… | Read |
|---|---|
| Understand the product and why | [`docs/product/vision.md`](docs/product/vision.md) |
| See what decisions are waiting on you | [`docs/DECISIONS-NEEDED.md`](docs/DECISIONS-NEEDED.md) |
| See the architecture | [`docs/architecture/overview.md`](docs/architecture/overview.md) |
| See what we build first | [`docs/plan/roadmap.md`](docs/plan/roadmap.md) |
| Know how we work (branches, specs, CI) | [`docs/engineering/how-we-work.md`](docs/engineering/how-we-work.md) |

## Repository layout

```
packages/common   shared models (profile, forms, runner protocol)
apps/server       API + agents + durable workflows (Python, FastAPI, DBOS)
apps/runner       local browser runner (Python, Playwright, your real Chrome)
apps/web          dashboard (Next.js)
docs/             product, research, architecture, ADRs, specs, runbooks
```

```bash
just bootstrap && just db && just migrate   # then: just server · just web · just runner · just test
```

See [`docs/engineering/repo-structure-and-ci.md`](docs/engineering/repo-structure-and-ci.md).
