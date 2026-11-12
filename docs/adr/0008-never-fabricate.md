# ADR-0008: Never fabricate — grounded generation with provenance

- Status: Accepted
- Date: 2026-11-12
- Related: NFR-1, FR-ANS-4, FR-TAIL-*

## Context
Submitting invented experience, skills, or facts harms the candidate (rescinded offers, reputation) and our brand. LLMs will fill gaps plausibly unless prevented structurally.

## Decision
- Every value in a Fill Plan and every claim in a tailored resume/cover letter must cite source IDs (profile fact IDs, answer IDs, user-provided answers, job/company facts for context only).
- A grounding checker (deterministic checks + LLM verifier) rejects outputs with uncited claims or with numbers/dates/titles not present in sources.
- Unknown → intervention, never a guess. Generated free text is marked `generated` and reviewed until the user opts into auto-approval.
- Yes/no eligibility questions (e.g. "Do you have 5 years of X?") are answered only from facts; ambiguous → ask.

## Consequences
+ Trust; defensible product promise; evidence bundles show provenance.
− More interventions early (mitigated by the answer bank learning).
