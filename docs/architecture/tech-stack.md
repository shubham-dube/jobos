# Tech stack

Status: In review — ADR-0002. Items marked **(decision)** are listed in DECISIONS-NEEDED.

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| Backend language | **Python 3.12+** | Best agent/browser ecosystem: Playwright, browser-use, JobSpy, DBOS, OpenRouter | TypeScript everywhere (Stagehand is TS) — weaker scraping/ML ecosystem |
| Frontend | **Next.js + TypeScript**, Tailwind, shadcn/ui, TanStack Query | Fast, standard, great DX; good for SaaS dashboard | SvelteKit, Remix |
| API | **FastAPI**, Pydantic v2, OpenAPI → generated TS client | Typed contracts shared web↔api | Django (heavier) |
| ORM / migrations | SQLAlchemy 2 (async) + Alembic | Mature | SQLModel |
| Workflows | **DBOS Transact** (ADR-0010, supersedes Temporal) | Durable on our Postgres, send/recv for HITL, partitioned queues, schedules | Temporal (extra infra), Inngest, Hatchet, Celery |
| DB | **PostgreSQL 16+ with pgvector** | One DB for relational + vectors; RLS for tenancy | separate vector DB (unnecessary) |
| Object storage | S3-compatible (Cloudflare R2 or AWS S3); MinIO for local dev | Cheap, standard | — |
| Browser | **Playwright + installed Google Chrome** (local runner) | Real browser, persistent contexts, tracing | Selenium, Puppeteer |
| Fallback agent | **browser-use** (MIT); Claude computer use for visual-only pages | Best OSS results; Python | Skyvern (AGPL — no) |
| LLM | **Provider plug-ins (ADR-0011)**: OpenRouter now (any model incl. Claude), Gemini later; per-task routing | Founder wants freedom of providers | Single-vendor SDK |
| LLM tracing/evals | **Langfuse** | OSS, self-hostable, prompt versioning + datasets | LangSmith, Braintrust |
| Resume rendering | **RenderCV** (Typst) | ATS-friendly PDFs from structured data | LaTeX, HTML→PDF |
| Discovery | httpx; Greenhouse/Lever/Ashby public APIs (built); **python-jobspy** next for LinkedIn/Indeed/Naukri | — | — |
| Auth | Staged (ADR-0013): owner token + dashboard password now; **Clerk** at Phase 3 | Secure for single owner, no vendor yet | Better Auth / Auth.js, Supabase Auth |
| Notifications | **WhatsApp Cloud API** (reply buttons) + **Resend** email (ADR-0012) | Founder's choice; one-tap answers on phone | Telegram, web push |
| Payments (P3) | Stripe (global) + Razorpay (India) | — | Paddle/Lemon Squeezy (merchant of record) |
| Observability | OpenTelemetry, Sentry, Grafana Cloud or Honeycomb, structlog | — | Datadog (cost) |
| Infra **(decision Q7)** | P1: Docker Compose. P3 recommendation: **AWS** (ECS Fargate, RDS Postgres, S3, KMS) or GCP equivalent; IaC with **OpenTofu/Terraform** | KMS + mature managed Postgres; India region available | Fly.io/Railway + Neon (simpler, cheaper early; weaker KMS story) |
| Runner packaging | P1 CLI via `uv`; P2 Tauri or PyInstaller desktop app with auto-update | — | Electron (heavier) |
| Extension (P3) | Chrome MV3, TypeScript, WXT/Plasmo framework | — | — |
| Tooling | `uv`, `pnpm`, `ruff`, `pyright`, `eslint`, `prettier`, `pytest`, `vitest`, Playwright Test, `pre-commit`, `just` | — | — |
| CI/CD | GitHub Actions, GHCR images, Renovate, CodeQL, gitleaks | — | — |

## Model usage policy (summary) — superseded by ADR-0011 for provider choice
- Default every agent to `claude-opus-5-5` (adaptive thinking; tune `effort` per route — Opus 5.5 defaults to `medium`, set explicitly).
- Use structured outputs (`output_config.format`) for all agent outputs; strict tool schemas.
- Prompt caching for the stable prefix (system prompt + master profile + answer bank summary).
- Handle `stop_reason == "refusal"`; enable server-side fallbacks.
- Cheaper models (`claude-sonnet-5-5`, `claude-haiku-5-5`) per route only after eval evidence + founder approval.
- Batch API (50% cost) for non-urgent bulk scoring (e.g. overnight matching).
