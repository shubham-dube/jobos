# Reliability and observability

Status: Draft

## 1. Service level objectives (P3 targets; measured from P1)

| SLO | Target |
|---|---|
| Dashboard/API availability | 99.5% monthly |
| Intervention notification latency (pause → notification sent) | p95 < 10 s |
| Discovery freshness (scheduled run completes) | 95% of runs within 30 min of schedule |
| Application workflow: no lost work | 100% (durable) |
| Adapter success rate (attempts reaching submit gate without UNKNOWN_PAGE) per ATS | ≥ 95% Greenhouse/Lever/Ashby; ≥ 85% Workday |
| Wrong-field rate (user-flagged) | < 0.5% of fields |

## 2. Failure handling

| Failure | Handling |
|---|---|
| Runner offline | Activities time out → applications stay `QUEUED`; user notified "runner offline"; resume on reconnect |
| Site timeout / 5xx | Retry with backoff (activity retry policy), max 3; then `FAILED (retryable)` re-queued later |
| Validation error after fill | Re-resolve the field(s) with the error message as context, once; then intervention |
| Adapter breaks (DOM drift) | Fall back to generic engine; open drift incident; canary alerts |
| LLM API error / rate limit | SDK retries; circuit breaker per model; degrade non-critical agents (e.g. skip match explanations) |
| Uncertain submission | Never auto-retry; wait for email confirmation or human |
| Bad deploy | Workflow versioning (Temporal patching / worker versioning) so in-flight workflows finish on compatible code; feature flags; quick rollback |

## 3. Idempotency
- Application uniqueness: `(candidate_id, job_id)` unique; plus company+normalized-title window check.
- Each activity has an idempotency key; side-effecting steps (submit) record intent before acting and check state after reconnects.

## 4. Observability stack
- **Tracing:** OpenTelemetry across web → API → Temporal → activities → runner. Trace id propagated in runner protocol messages. One trace per attempt.
- **LLM tracing & evals:** Langfuse — every call with prompt version, model, tokens (incl. cache hits), cost, latency, linked to `application_id`.
- **Errors:** Sentry for API, worker, runner, web.
- **Metrics:** funnel counts by state, adapter success by ATS, interventions by type, cost per application, runner online ratio, queue depth.
- **Logs:** structured JSON (structlog), PII-redacted.
- **Product analytics (P3):** PostHog (self-hostable) or similar, privacy-respecting.

## 5. Drift detection (critical for this product)
- **Nightly canaries** per ATS: pick N live public postings, run extract + resolve + fill in **dry-run** (never submit), compare FormSchema shape to last known; alert on new unknown field types, missing selectors, failures.
- Production signal: spike in `UNKNOWN_PAGE` or validation errors per ATS → alert.
- Adapter version recorded on every attempt for fast blame.

## 6. Backups & DR
- Postgres PITR (managed), daily snapshot test-restores (P3).
- Object storage versioning for evidence bundles.
- Temporal Cloud handles workflow history durability (or self-hosted with its own DB backups).
- RPO 15 min / RTO 4 h for P3.
