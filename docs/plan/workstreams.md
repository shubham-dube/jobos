# Workstreams and spec backlog

Status: Draft. Each row becomes `docs/specs/NNNN-slug/` when started. Order = recommended build order; dependencies in the last column.

## Workstreams
| WS | Name | Owns |
|---|---|---|
| WS-A | Platform foundations | repo, CI, infra, auth, tenancy, observability |
| WS-B | Profile & answer bank | profile import/edit, documents, presets, answer bank |
| WS-C | Discovery | sources, normalization, dedup, ATS resolution |
| WS-D | Verification & matching | legitimacy score, fit score, feedback |
| WS-E | Runner | runner protocol, local runner, sessions, packaging; cloud runner later |
| WS-F | Form engine & adapters | extract/resolve/gate/fill/verify, adapters, navigator, fixtures, canaries |
| WS-G | Workflows & HITL | Temporal workflows, state machine, interventions, notifications |
| WS-H | Inbox | mailbox connections, classification, linking, OTP |
| WS-I | Dashboard | web app |
| WS-J | Tailoring | resume variants, cover letters, grounding checker |
| WS-K | Commercial | billing, onboarding, legal docs, analytics |

## Spec backlog

| # | Spec | WS | Phase | Depends on |
|---|---|---|---|---|
| 0001 | Repo scaffolding, toolchains, justfile, Compose, pre-commit | A | 0 | — |
| 0002 | CI pipeline (lint/type/test/security/license) + branch protection | A | 0 | 0001 |
| 0003 | Core domain package: IDs, tenancy, application state machine, events | A/G | 0 | 0001 |
| 0004 | DB schema v1 + migrations + RLS | A | 0 | 0003 |
| 0005 | LLM gateway package (Claude client, structured outputs, caching, budgets, Langfuse) | A | 0 | 0001 |
| 0006 | Runner protocol v0 + local runner skeleton (pairing, Chrome persistent profile, heartbeat) | E | 0 | 0004 |
| 0007 | Observability baseline (OTel, Sentry, structlog redaction) | A | 0 | 0001 |
| 0010 | Master profile schema + resume import (Profile Builder) | B | 1 | 0004, 0005 |
| 0011 | Profile/documents/presets API + dashboard editor | B/I | 1 | 0010 |
| 0012 | Answer bank: storage, embeddings, matching, API | B | 1 | 0004, 0005 |
| 0013 | Interventions + InterventionWorkflow + Telegram bot + web push | G | 1 | 0003, 0012 |
| 0014 | Search profiles & policies | C/G | 1 | 0004 |
| 0015 | Sources: Greenhouse/Lever/Ashby connectors + company list bootstrap | C | 1 | 0004 |
| 0016 | Sources: JobSpy connector (read-only) + paste-a-URL | C | 1 | 0015 |
| 0017 | Job-alert email parsing (forward/Gmail for founder) | C/H | 1 | 0015 |
| 0018 | Normalization, dedup, direct-to-ATS resolution | C | 1 | 0015 |
| 0019 | Verification v1 + liveness check | D | 1 | 0018 |
| 0020 | Matching v1 + feedback | D | 1 | 0018, 0010 |
| 0021 | Form engine core: FormSchema, Fill Plan, resolver chain, submit gate, evidence | F | 1 | 0012, 0005 |
| 0022 | Fixture library + fake-ATS server + cassette LLM testing | F | 1 | 0021 |
| 0023 | Adapter: Greenhouse | F | 1 | 0021, 0022 |
| 0024 | Adapter: Lever | F | 1 | 0023 |
| 0025 | Adapter: Ashby | F | 1 | 0023 |
| 0026 | ApplicationWorkflow + ApplyBudgetWorkflow + pacing | G | 1 | 0013, 0021, 0006 |
| 0027 | Session health + Connections page | E/I | 1 | 0006 |
| 0028 | Dashboard v1: feed, pipeline, application detail, intervention inbox | I | 1 | 0019, 0020, 0026 |
| 0030 | Adapter: Workday (+ account creation, vault) | F/E | 2 | 0023, vault |
| 0031 | Credential vault (envelope encryption) | A | 2 | 0004 |
| 0032 | Generic extractor + Navigator fallback (browser-use, restricted tools) | F | 2 | 0021 |
| 0033 | Inbox tracking: classification, linking, status automation, OTP | H | 2 | 0017, 0026 |
| 0034 | Adapters: SmartRecruiters, iCIMS, Workable | F | 2 | 0032 |
| 0035 | Adapters: Google Forms, Microsoft Forms | F | 2 | 0021 |
| 0036 | Tailoring + grounding checker + RenderCV | J | 2 | 0010 |
| 0037 | Drift canaries | F | 2 | 0022 |
| 0038 | Ghost-job signals + more sources | C/D | 2 | 0019 |
| 0039 | Runner desktop packaging + auto-update | E | 2 | 0006 |
| 0040 | Opt-in platform-native apply (Naukri / LinkedIn Easy Apply) | F | 2 | founder decision Q4 |
| 0041 | Analytics v1 | I | 2 | 0033 |
| 0050+ | Phase 3: auth/multi-tenant onboarding, billing, cloud runner, forwarding inbox, extension, legal, hardening | A/E/K | 3 | — |
