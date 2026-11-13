# ADR-0010: DBOS (Postgres-backed) for durable workflows

- Status: Accepted
- Date: 2026-11-13
- Supersedes: ADR-0003
- Related: agents-and-workflows.md, FR-HITL-5, NFR-2

## Context
We need durable, resumable workflows that pause for humans (hours/days), retry safely, run on schedules, and pace work per employer. The founder's machine is Windows and Phase 1–2 run locally. Temporal requires a separate server cluster (or Temporal Cloud) and its test server binary download is not available in all of our environments.

## Options
1. Temporal — powerful, but extra infra to run and operate.
2. **DBOS Transact (MIT)** — durable workflows/steps as a Python library; state checkpointed in **our existing Postgres**; `send/recv` for human signals with timeouts; durable `sleep`; queues with global/worker concurrency, rate limits and **per-partition concurrency/limits** (perfect for per-employer pacing); schedules; `DBOSClient` to enqueue/signal from other processes.
3. Celery/RQ — not durable enough.

## Decision
DBOS. One Postgres holds app data and workflow state. The API process uses `DBOSClient` to enqueue workflows and send signals; worker processes run `DBOS.launch()`. For local use one process can run both roles (`jobos serve --role all`).

## Consequences
+ Zero extra infrastructure; runs on Windows; easy to test (just Postgres).
+ Horizontal scale by adding worker processes (DBOS coordinates queues through Postgres).
− Very high scale puts load on Postgres; revisit (Temporal/sharding) above ~1M workflow steps/day.
− Workflow code must be deterministic (same rule as Temporal): all I/O inside `@DBOS.step`.
