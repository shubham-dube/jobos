# ADR-0015: Founder-configurable auto-approval rules

- Status: Accepted
- Date: 2026-11-13
- Related: FR-POL-1, FR-APP-5, form-filling-engine.md §8

## Context
Founder: "at first everything must be in review, and when I say, it must auto-submit. It must be my config what is approved automatically and what goes to review."

## Decision
- The submit gate's hard checks (required fields filled, no validation errors, provenance, duplicates, caps, liveness) always apply.
- After hard checks, an ordered list of **approval rules** decides `auto_submit` vs `review`. First matching rule wins; **default = review**.
- Rule conditions (all optional, AND-ed): `ats_in`, `site_in`, `company_in` / `company_not_in`, `min_match_score`, `min_legitimacy`, `countries_in`, `remote_only`, `max_generated_fields` (free-text written by AI), `max_low_confidence_fields`, `answer_sources_subset_of` (e.g. only `profile`, `preset`, `answer_bank`), `platform_native` (Easy Apply etc.).
- Rules are edited in the dashboard Settings page and stored per candidate; every gate decision records which rule matched.

Example: "auto-submit Greenhouse/Lever/Ashby when match ≥ 75, no AI-written text, all answers from profile/answer bank; everything else review."

## Consequences
+ Founder controls autonomy precisely and can widen it gradually.
