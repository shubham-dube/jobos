# Repository structure, CI/CD, environments

Status: In review

## 1. Layout

```
jobos/
├─ AGENTS.md / CLAUDE.md          # standing rules for coding agents
├─ justfile                       # unified commands: just dev, just test, just lint, just e2e
├─ docker-compose.yml             # postgres, temporal (dev), minio, api, worker, web, langfuse (optional)
├─ .env.example
├─ apps/
│  ├─ web/                        # Next.js dashboard
│  ├─ api/                        # FastAPI service (+ Telegram webhook, runner gateway)
│  ├─ worker/                     # Temporal workers (workflows + activities)
│  └─ runner/                     # local runner (Playwright + Chrome), later desktop shell
├─ packages/
│  ├─ core/                       # domain models, state machine, policies, schemas
│  ├─ llm/                        # Claude client wrapper, prompts, routing, budgets, tracing
│  ├─ form-engine/                # extract/resolve/gate/fill/verify, generic extractor, navigator
│  ├─ ats-adapters/               # greenhouse/, lever/, ashby/, workday/, google_forms/ …
│  ├─ sources/                    # discovery connectors, normalization, dedup, resolution
│  └─ ts-client/                  # generated OpenAPI client for web
├─ tests/
│  ├─ fixtures/forms/<ats>/<case>/  # saved HTML + golden schema/plan
│  ├─ fake-ats/                     # local server replaying multi-page ATS flows
│  ├─ evals/                        # LLM eval datasets + runners
│  └─ e2e/                          # Playwright tests: dashboard + full apply against fake-ats
├─ infra/
│  ├─ docker/                     # Dockerfiles
│  └─ tofu/                       # IaC (P3)
├─ docs/
└─ .github/
   ├─ workflows/                  # ci.yml, nightly.yml, release.yml, codeql.yml
   ├─ pull_request_template.md
   └─ ISSUE_TEMPLATE/
```

Python: one `uv` workspace (root `pyproject.toml` with members). TS: `pnpm` workspace for `apps/web`, `packages/ts-client`.

## 2. CI (GitHub Actions)

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | PR, push to main | path-filtered: **py-lint** (ruff, pyright), **py-test** (pytest with Postgres + Temporal test server via services), **web** (eslint, tsc, vitest, build), **engine** (form-engine tests against fixtures + fake-ats with headless Chromium), **contracts** (OpenAPI schema diff → regenerate client check), **security** (gitleaks, pip-audit, pnpm audit, license check), **docker build** |
| `nightly.yml` | cron | LLM evals (budget-capped), **ATS drift canaries (dry-run, never submit)**, dependency audit, e2e full suite |
| `codeql.yml` | PR + weekly | CodeQL for Python & JS |
| `release.yml` | tag | build/push images to GHCR, deploy prod (P3), runner app build/sign (P2) |

Rules: Actions pinned by commit SHA; least-privilege `permissions:`; secrets only in protected environments; Renovate for updates (grouped weekly).

## 3. Environments

| Env | Purpose | Data | Deploy |
|---|---|---|---|
| local | dev | seed/fake | `just dev` (Compose) |
| CI | tests | ephemeral | per run |
| staging (P2/P3) | integration, founder dogfood | founder's real data allowed only if founder wants it there; otherwise synthetic | auto from `main` |
| production (P3) | customers | real | release tags, manual approval |

Preview deployments for the web app per PR (Vercel or equivalent) once the dashboard exists.

## 4. Local developer experience
- `just bootstrap` → installs uv/pnpm deps, pre-commit hooks, Playwright browsers for tests.
- `just dev` → starts Compose stack + web dev server + worker with reload.
- `just runner` → starts local runner against local API using real Chrome with profile at `~/.jobos/profiles/dev`.
- `just test`, `just lint`, `just e2e`, `just evals`.
- Dev container (`.devcontainer/`) so cloud agents and the founder get identical environments.
