# Tech stack

Status: In review — ADR-0002. Items marked **(decision)** are listed in DECISIONS-NEEDED.

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| Backend language | **Python 3.12+** | Best agent/browser ecosystem: Playwright, browser-use, JobSpy, Anthropic SDK, Temporal SDK | TypeScript everywhere (Stagehand is TS) — weaker scraping/ML ecosystem |
| Frontend | **Next.js + TypeScript**, Tailwind, shadcn/ui, TanStack Query | Fast, standard, great DX; good for SaaS dashboard | SvelteKit, Remix |
| API | **FastAPI**, Pydantic v2, OpenAPI → generated TS client | Typed contracts shared web↔api | Django (heavier) |
| ORM / migrations | SQLAlchemy 2 (async) + Alembic | Mature | SQLModel |
| Workflows | **Temporal** (ADR-0003) | Durable, signals for HITL, schedules, retries, versioning | Inngest, Hatchet, Celery+Redis (not durable enough), LangGraph persistence (agent-level only) |
| DB | **PostgreSQL 16+ with pgvector** | One DB for relational + vectors; RLS for tenancy | separate vector DB (unnecessary) |
| Object storage | S3-compatible (Cloudflare R2 or AWS S3); MinIO for local dev | Cheap, standard | — |
| Browser | **Playwright + installed Google Chrome** (local runner) | Real browser, persistent contexts, tracing | Selenium, Puppeteer |
| Fallback agent | **browser-use** (MIT); Claude computer use for visual-only pages | Best OSS results; Python | Skyvern (AGPL — no) |
| LLM | **Anthropic Claude via official Python SDK**, default `claude-opus-5-5`, adaptive thinking, structured outputs, prompt caching | Strong tool use/computer use; one vendor simplifies evals | Multi-provider gateway later if needed |
| LLM tracing/evals | **Langfuse** | OSS, self-hostable, prompt versioning + datasets | LangSmith, Braintrust |
| Resume rendering | **RenderCV** (Typst) | ATS-friendly PDFs from structured data | LaTeX, HTML→PDF |
| Discovery | httpx, selectolax, **python-jobspy** | — | — |
| Auth **(decision Q8)** | Recommend **Clerk** (Google sign-in, MFA, orgs for agency mode; JWT verified in FastAPI via JWKS) | Fastest secure path | Better Auth / Auth.js (self-hosted), Supabase Auth |
| Notifications | Web Push (VAPID), **Telegram Bot API**, email via Resend/Postmark/SES | Telegram = instant one-tap answers on phone | WhatsApp Business (P4, cost/approval) |
| Payments (P3) | Stripe (global) + Razorpay (India) | — | Paddle/Lemon Squeezy (merchant of record) |
| Observability | OpenTelemetry, Sentry, Grafana Cloud or Honeycomb, structlog | — | Datadog (cost) |
| Infra **(decision Q7)** | P1: Docker Compose. P3 recommendation: **AWS** (ECS Fargate, RDS Postgres, S3, KMS) or GCP equivalent; Temporal Cloud; IaC with **OpenTofu/Terraform** | KMS + mature managed Postgres; India region available | Fly.io/Railway + Neon (simpler, cheaper early; weaker KMS story) |
| Runner packaging | P1 CLI via `uv`; P2 Tauri or PyInstaller desktop app with auto-update | — | Electron (heavier) |
| Extension (P3) | Chrome MV3, TypeScript, WXT/Plasmo framework | — | — |
| Tooling | `uv`, `pnpm`, `ruff`, `pyright`, `eslint`, `prettier`, `pytest`, `vitest`, Playwright Test, `pre-commit`, `just` | — | — |
| CI/CD | GitHub Actions, GHCR images, Renovate, CodeQL, gitleaks | — | — |

## Model usage policy (summary)
- Default every agent to `claude-opus-5-5` (adaptive thinking; tune `effort` per route — Opus 5.5 defaults to `medium`, set explicitly).
- Use structured outputs (`output_config.format`) for all agent outputs; strict tool schemas.
- Prompt caching for the stable prefix (system prompt + master profile + answer bank summary).
- Handle `stop_reason == "refusal"`; enable server-side fallbacks.
- Cheaper models (`claude-sonnet-5-5`, `claude-haiku-5-5`) per route only after eval evidence + founder approval.
- Batch API (50% cost) for non-urgent bulk scoring (e.g. overnight matching).
