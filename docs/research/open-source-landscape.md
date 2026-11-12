# Open-source landscape — build vs. reuse

Status: Draft (Nov 2026). **Verify license and maintenance status in each repo before adopting** — some details below come from secondary sources.

Policy (ADR-0009): we may *depend on* permissive (MIT/Apache/BSD) libraries; we may *study* AGPL/GPL projects for ideas but not copy their code into our proprietary codebase, and not link them into the SaaS.

## 1. Browser automation & agents

| Project | Lang | License | What it gives us | Decision |
|---|---|---|---|---|
| **Playwright** | Py/TS | Apache-2.0 | Reliable browser control, persistent contexts, tracing | **Use — foundation** |
| **browser-use** | Py | MIT | LLM agent over DOM/a11y tree; strong WebVoyager results; biggest community | **Use as generic fallback agent** (behind our own tool permissions — it never gets submit) |
| Stagehand | TS | MIT | AI primitives (act/extract/observe) on Playwright, action caching | Study the caching idea; TS-only conflicts with Python backend |
| Skyvern | Py | AGPL-3.0 | Vision-based agent, has a "Jobs Agent" and credential APIs | **Do not embed** (AGPL). Study; could be used as an external service only after ADR |
| Claude computer use (`computer_toolset_20260801`) | API | commercial API | Vision-based control for pages with no usable DOM | Last-resort fallback; costly |
| Steel browser | — | Apache-2.0 | Self-hostable browser API with persistent profiles, sessions, live view | **Candidate for self-hosted cloud runner (P3)** |
| Browserbase / Kernel / Hyperbrowser / Steel Cloud | — | managed | Cloud browsers with persistent profiles/contexts, proxies, live view | Candidates for P3 cloud runner (buy vs. build decision then) |

## 2. Job discovery

| Project | License | Use |
|---|---|---|
| **python-jobspy** (speedyapply/JobSpy) | MIT | LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Naukri, Bayt search. Rate-limited, LinkedIn needs proxies, ~1000 results cap per board. **Use, wrapped as one source connector; isolate failures.** |
| Greenhouse / Lever / Ashby / Workable / SmartRecruiters public job APIs | vendor public APIs | **Use directly** (no scraping needed). See job-sources.md |
| Apify ATS actors | commercial | Not needed — endpoints are public; maybe as reference for company-slug lists |

## 3. Job-application projects (study, don't copy)

| Project | License | Notes |
|---|---|---|
| ApplyPilot | AGPL-3.0 | End-to-end pipeline incl. Claude-driven auto-apply; limited LinkedIn support. Good reference for pipeline stages. |
| AIHawk Auto_Jobs_Applier (and forks) | check repo (was AGPL) | Reportedly dropped LinkedIn after LinkedIn objected — a signal on platform risk. |
| ai-job-search (MadsLorentzen) | MIT | Drafter–reviewer agent pattern; human-in-the-loop; no auto-submit. Good prompts/pattern reference. |
| career-ops, jobpilot, Orbitapply | various | Local-first designs; read for UX ideas. |
| Naukri-autoapply-bot | check | Selenium Naukri flows; shows 2026 Naukri DOM; warns of restrictions. |

## 4. Resume & documents

| Project | License | Use |
|---|---|---|
| **RenderCV** | MIT | YAML → PDF via Typst; ATS-friendly templates. **Use for tailored resume rendering.** |
| JSON Resume schema | MIT | **Use as base of master-profile schema** (we extend it). |
| pypdf / pdfplumber / docx2python | permissive | Resume parsing input (LLM does the structuring). |

## 5. Platform building blocks

| Need | Choice | License |
|---|---|---|
| Durable workflows + HITL waits | **Temporal** (Python SDK) | MIT |
| LLM tracing, prompt mgmt, evals | **Langfuse** (self-host or cloud) | MIT (core) |
| Vector search | **pgvector** | PostgreSQL license |
| Migrations / ORM | SQLAlchemy 2 + Alembic | MIT |
| API | FastAPI + Pydantic v2 | MIT |
| Web UI | Next.js + shadcn/ui + Tailwind | MIT |
| Telegram notifications | python-telegram-bot / aiogram | LGPL/MIT — use as dependency only |
| Observability | OpenTelemetry, Sentry SDK | Apache/MIT |
| Object storage (local) | MinIO | AGPL — **dev-only container**, not shipped/linked; prod uses S3/R2 |

## 6. Build-vs-buy summary
- **Build (our core IP):** form engine (extract/resolve/gate/fill/verify), ATS adapters, answer bank, verification scoring, workflow orchestration, dashboard, runner protocol.
- **Reuse:** Playwright, browser-use (fallback), JobSpy, ATS public APIs, RenderCV, Temporal, Langfuse, pgvector.
- **Buy later if cheaper than building:** cloud browsers + proxies (P3), email deliverability, auth (DECISIONS-NEEDED Q8).
