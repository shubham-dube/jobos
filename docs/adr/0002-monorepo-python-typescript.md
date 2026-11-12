# ADR-0002: Monorepo with Python backend/agents and TypeScript web

- Status: Proposed
- Date: 2026-11-12
- Related: tech-stack.md

## Context
Agent and browser tooling (Playwright, browser-use, JobSpy, Temporal, Anthropic SDK) is strongest in Python. The dashboard benefits from the React/Next.js ecosystem. One founder + agents → one repo is easiest to keep consistent.

## Options
1. **Monorepo, Python (uv workspace) + TS (pnpm workspace)** with OpenAPI-generated client.
2. TypeScript everywhere (Stagehand, Temporal TS SDK).
3. Polyrepo.

## Decision
Option 1. `apps/{web,api,worker,runner}`, `packages/{core,form-engine,ats-adapters,sources,llm}` (Python), `packages/ts-client` (generated). A `justfile` provides unified commands. CI uses path filters so only affected parts run.

## Consequences
+ Best libraries for the hard parts; one place for docs/specs; atomic cross-cutting PRs.
− Two toolchains. Mitigated by a dev container / Docker Compose and `just` recipes.
Revisit if the web needs server-side logic beyond the API (keep business logic in Python).
