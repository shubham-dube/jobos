# ADR-0011: Pluggable LLM providers with per-task model routing

- Status: Accepted
- Date: 2026-11-13
- Supersedes the single-vendor parts of tech-stack.md "Model usage policy"

## Context
The founder wants to add providers freely: **OpenRouter now** (access to any model), **Gemini later**, maybe others. Tasks differ widely in difficulty and volume (classifying 1,000 emails vs. writing a cover letter). Testing budget is small ($5).

## Decision
- `jobos.llm` defines a `LLMProvider` protocol: `complete(request) -> response` with messages, JSON-schema structured output, temperature/max tokens, and usage (tokens, cost).
- Implementations: `OpenRouterProvider` (OpenAI-compatible Chat Completions over HTTPS; `response_format: json_schema`), `FakeProvider` (tests). `GeminiProvider` slot reserved.
- A `ModelRouter` maps **task names** (e.g. `profile.extract`, `job.match`, `form.resolve`, `form.navigate`, `email.classify`, `text.generate`) to `provider:model` + params from config (`JOBOS_LLM_ROUTES` JSON / settings table), with a default route.
- Every call: Pydantic validation of structured output (one repair retry), cost + token ledger row (`llm_calls`), per-run and per-day budget guard, PII-aware logging (no prompt bodies at INFO).
- Defaults (changeable in settings): high-volume/simple tasks → `anthropic/claude-haiku-5.5`; judgment tasks (form resolve, match, generate) → `anthropic/claude-sonnet-5.5`. Tests and live smoke tests always use `anthropic/claude-haiku-5.5`.

## Consequences
+ Swap models/providers per task without code changes; cost visible per application.
− Provider differences in structured-output support → provider adapters normalize; fallback to "JSON in text" parsing when a model lacks json_schema.
