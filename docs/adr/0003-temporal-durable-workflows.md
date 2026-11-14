# ADR-0003: Temporal for durable workflows and human-in-the-loop

- Status: Superseded by ADR-0010
- Date: 2026-11-12
- Related: agents-and-workflows.md, FR-HITL-5, NFR-2

## Context
An application can take minutes of browser work and then wait days for a human answer, a login, or an email confirmation. Steps must retry safely without double-submitting. We need schedules (discovery), timers (reminders/expiry), signals (answers), and safe deploys while workflows are in flight.

## Options
1. **Temporal** — durable execution, signals, timers, schedules, retries, versioning; Python SDK; Temporal Cloud or self-host.
2. Inngest / Hatchet — simpler, step functions, good DX; less mature for very long waits/versioning in Python.
3. Celery/RQ + DB state machine — we'd rebuild durability, timers, and signals ourselves.
4. LangGraph checkpoints — agent-level persistence, not a general workflow engine.

## Decision
Temporal. Local dev uses `temporal server start-dev`; production uses Temporal Cloud (or self-hosted if cost requires).

## Consequences
+ Interventions are natural (`await workflow.wait_condition` on a signal); retries/timeouts declarative; full history for debugging.
− Learning curve; determinism rules for workflow code; another piece of infra.
Revisit if Temporal Cloud costs exceed ~5% of revenue at scale.
