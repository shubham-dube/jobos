# ADR-0001: Docs-first, spec-driven development with AI coding agents

- Status: Accepted
- Date: 2026-11-12
- Deciders: Founder, Claude

## Context
The founder wants a production-grade product built largely with AI coding agents, without forgetting requirements or decisions. Unstructured prompting ("vibe coding") produces drift between intent and code. The 2026 practice that works is spec-driven development: humans own decisions and acceptance criteria; agents implement against written specs; standing rules live in `AGENTS.md`.

## Decision
- Every unit of work has `docs/specs/NNNN-slug/{spec.md, plan.md, tasks.md}` (format inspired by GitHub Spec Kit). The founder approves `spec.md` (what/why/acceptance); agents may draft `plan.md`/`tasks.md` and implement.
- Decisions are ADRs. Requirements have IDs (PRD). `AGENTS.md` holds standing rules; `CLAUDE.md` imports it.
- Docs are updated in the same PR as the code.

## Consequences
+ Agents (and humans) have unambiguous context; decisions aren't re-litigated.
+ Review effort moves earlier (spec review) where it's cheaper.
− Overhead for tiny changes → exempt: typo/dep bumps/small fixes need only a PR description.
Revisit if specs routinely go stale or slow us down more than they help.
