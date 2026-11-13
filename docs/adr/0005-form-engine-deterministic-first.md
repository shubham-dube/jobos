# ADR-0005: Deterministic adapters + structured fill plans; single submit gate

- Status: Accepted
- Date: 2026-11-12
- Related: form-filling-engine.md, FR-APP-*, NFR-1

## Context
Fully autonomous LLM browser agents are flexible but slow, costly per step, non-deterministic, hard to test, and can be steered by prompt injection. Most applications run on a handful of ATSs whose forms are structurally predictable.

## Decision
1. Separate **understanding** from **acting**: extract a typed FormSchema → LLM resolves a typed Fill Plan (values + sources + confidence) → code fills and verifies.
2. Deterministic **adapters** per major ATS; generic extractor + bounded Navigator agent as fallback.
3. A single **submit gate** issues an unforgeable `GateToken`; only `adapter.submit(gate_token)` can click final submit. LLM agents never have submit capability.

## Consequences
+ Testable with fixtures; cheap per application; auditable provenance; strong injection resistance.
− Adapter maintenance (drift) → canaries and fallback required.
− Upfront engineering for each ATS.
Revisit per ATS if generic engine success rate approaches adapter success rate at similar cost.
