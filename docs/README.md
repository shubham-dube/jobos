# Documentation index

All planning, design and decisions live here. Docs are written **before** code and kept in sync with it.

## Status legend
Every doc starts with a status line:
- `Draft` — being written, expect changes
- `In review` — waiting for the founder's review/decision
- `Approved` — agreed; changes need a PR with rationale
- `Superseded by X` — kept for history

## Map

### 0. Start here
- [DECISIONS-NEEDED.md](DECISIONS-NEEDED.md) — **open decisions that block work. Review first.**
- [glossary.md](glossary.md) — shared vocabulary

### 1. Product (what and why)
- [product/vision.md](product/vision.md) — problem, vision, principles, north-star metric
- [product/market-and-competitors.md](product/market-and-competitors.md) — landscape, pricing, gaps
- [product/opportunity-map.md](product/opportunity-map.md) — adjacent problems, what else to build, scoring
- [product/prd-mvp.md](product/prd-mvp.md) — requirements with IDs (FR/NFR), scope in/out
- [product/business-model.md](product/business-model.md) — pricing, unit economics, go-to-market

### 2. Research (what exists)
- [research/open-source-landscape.md](research/open-source-landscape.md) — build vs. reuse, licenses
- [research/job-sources.md](research/job-sources.md) — where jobs come from and how to get them
- [research/risk-legal-compliance.md](research/risk-legal-compliance.md) — ToS, privacy law, Google verification, bans

### 3. Architecture (how)
- [architecture/overview.md](architecture/overview.md) — system context, components, data flow
- [architecture/agents-and-workflows.md](architecture/agents-and-workflows.md) — agents, durable workflows, state machines, human-in-the-loop
- [architecture/browser-execution.md](architecture/browser-execution.md) — runners, real browser profiles, sessions, logins
- [architecture/form-filling-engine.md](architecture/form-filling-engine.md) — extract → resolve → gate → fill → verify → submit
- [architecture/data-model.md](architecture/data-model.md) — entities, tables, master profile schema
- [architecture/security-and-privacy.md](architecture/security-and-privacy.md) — threat model, secrets, prompt injection
- [architecture/reliability-observability.md](architecture/reliability-observability.md) — SLOs, retries, drift detection, tracing
- [architecture/tech-stack.md](architecture/tech-stack.md) — chosen tools and why

### 4. Decisions
- [adr/](adr/) — Architecture Decision Records (one decision per file)

### 5. Engineering (how we work)
- [engineering/how-we-work.md](engineering/how-we-work.md) — workflow from idea to production
- [engineering/repo-structure-and-ci.md](engineering/repo-structure-and-ci.md) — monorepo, CI/CD, environments
- [engineering/testing-strategy.md](engineering/testing-strategy.md) — test pyramid, fixtures, LLM evals, drift canaries

### 6. Plan (what next)
- [plan/roadmap.md](plan/roadmap.md) — phases and exit criteria
- [plan/workstreams.md](plan/workstreams.md) — workstreams, dependencies, spec list
- [specs/](specs/) — one folder per unit of work (`spec.md`, `plan.md`, `tasks.md`)
