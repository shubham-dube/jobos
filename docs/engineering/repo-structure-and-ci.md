# Repository structure, CI/CD, environments

Status: In review

## 1. Layout (as built)

```
jobos/
├─ AGENTS.md / CLAUDE.md            # standing rules for coding agents
├─ pyproject.toml / uv.lock         # uv workspace (packages/common, apps/server, apps/runner)
├─ justfile · docker-compose.yml · .env.example
├─ packages/common/                 # jobos_common: MasterProfile, FormPage/FillPlan, runner protocol v1
├─ apps/server/                     # jobos: API + workflows + agents (one package, roles api|worker|all)
│  └─ src/jobos/
│     ├─ api/          dashboard.py, runner.py (protocol), webhooks.py (WhatsApp), app.py
│     ├─ workflows/    application.py, discovery.py, inbox.py, navigator.py, primitives.py, runtime.py (DBOS)
│     ├─ forms/        taxonomy.py, answer_bank.py, resolver.py, gate.py, recipes.py
│     ├─ matching/     geo.py, rules.py (filters/eligibility/legitimacy), scorer.py (LLM)
│     ├─ sources/      ats.py (Greenhouse/Lever/Ashby), base.py, seed_companies.json
│     ├─ services/     applications, candidates, discovery, inbox (IMAP), interventions, runner_gateway, storage, secrets
│     ├─ llm/          gateway.py (routing/budget/ledger), openrouter.py, fake.py
│     ├─ notify/       WhatsApp Cloud API + Resend
│     └─ db/           models.py, migrations/ (Alembic)
│  └─ tests/          unit + e2e (fake ATS fixture in tests/fixtures/fake_ats)
├─ apps/runner/                     # jobos_runner: installs on the user's PC (Windows), drives real Chrome
│  └─ src/jobos_runner/  agent.py (long-poll loop), page_ops.py, js/extract.js, human.py, browser.py, cli.py
├─ apps/web/                        # Next.js dashboard (server components; API token stays server-side)
├─ infra/docker/                    # server image
└─ docs/
```

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
