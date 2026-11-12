# Testing strategy

Status: In review

Testing a product that drives real websites with an LLM needs more than unit tests. Five layers:

## 1. Unit tests (fast, every PR)
- Domain logic: state machine transitions, policies, dedup/fuzzy matching, normalization, scoring rules, grounding checker, submit gate.
- Property-based tests (Hypothesis) for normalizers and state machine invariants (e.g. "no path reaches SUBMITTED twice").

## 2. Integration tests (every PR)
- API + Postgres (real Postgres in CI service container; testcontainers locally).
- Temporal workflows with the time-skipping test environment: interventions, timeouts, retries, `UNCERTAIN` handling, versioning.
- Runner protocol: fake runner implementing the protocol.
- Tenancy: tests that attempt cross-tenant reads must fail (RLS).

## 3. Form-engine tests against fixtures (every PR)
- **Fixture library**: saved HTML (+ assets) of real application forms per ATS, captured from public postings, scrubbed of employer-specific data where needed. Each case has golden `form_schema.json` and, given a test profile, golden `fill_plan.json`.
- **Fake ATS server** (`tests/fake-ats`): replays multi-page flows (Workday-like account creation, validation errors, conditional questions, file uploads, success page). Engine runs end-to-end against it in headless Chromium, including the submit gate and evidence bundle.
- LLM calls in these tests are **recorded/replayed** (cassettes) for determinism; a nightly job re-records with live calls to catch model behavior changes.

## 4. LLM evals (nightly + on prompt/model changes)
Datasets in `tests/evals/` (Langfuse datasets mirror them):

| Eval | Measures | Gate |
|---|---|---|
| Resume → profile extraction | field-level precision/recall | ≥ 0.95 on key fields |
| Question → answer-bank match | correct reuse vs. ask | false-reuse ≤ 1% |
| Form resolution | correct value per field on fixture forms | ≥ 98% correct, 0 fabricated |
| Grounding / fabrication red-team | outputs with uncited claims | 0 |
| Prompt-injection suite (pages, JDs, emails) | any unsafe proposal accepted by code | 0 |
| Match scoring | agreement with founder labels | track; improve over time |
| Email classification | accuracy per class | ≥ 95% |
| Verification (scam/ghost) | precision/recall on labeled set | track |

Any model or prompt change (including model routing — DECISIONS-NEEDED Q9) must show eval results in the PR.

## 5. Live checks (never submit)
- **Nightly drift canaries** on live public postings per ATS: navigate, extract, resolve, fill in dry-run; stop before submit; alert on failures/new field types.
- **Founder dogfooding** = the real end-to-end test; every founder-flagged issue becomes a fixture or eval case (regression).

## 6. UI tests
- Component tests (vitest + Testing Library); Playwright e2e for key journeys (onboarding, answering an intervention, reviewing and approving an application).

## 7. Non-functional
- Load test discovery + workflow throughput before P3 (k6/Locust): 1k candidates × daily cycle.
- Chaos: kill runner mid-application → resumes correctly, never double-submits.
