# JobOS (working name)

> An autopilot for the job search: agents that **find** real jobs that fit you, **verify** they are legitimate, **apply** through a real browser using your own logged-in accounts, **track** every reply in your inbox, and **stop and ask you** whenever they are missing information.

Status: **Phase 0 — documentation and decisions.** No product code yet. Start with [`docs/README.md`](docs/README.md).

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

## Repository layout (planned)

```
apps/        web (dashboard), api, worker (workflows), runner (browser executor)
packages/    shared Python/TS libraries: core domain, form engine, ATS adapters, sources, llm
infra/       docker, IaC
docs/        product, research, architecture, ADRs, specs, plans
```

See [`docs/engineering/repo-structure-and-ci.md`](docs/engineering/repo-structure-and-ci.md).
