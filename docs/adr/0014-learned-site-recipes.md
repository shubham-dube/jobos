# ADR-0014: Agents learn site recipes for recurring sites

- Status: Accepted
- Date: 2026-11-13
- Related: ADR-0005, form-filling-engine.md

## Context
The founder: "if no adapter exists, the agent fills the form itself, and captures what's needed to make an adapter for that website if it's not a one-time website." Hand-written adapters don't scale to thousands of employer sites.

## Decision
Three layers of site knowledge, tried in order:
1. **Coded adapters** for big ATS platforms (Greenhouse, Lever, Ashby, Workday…) — hand-written, tested with fixtures.
2. **Learned recipes** (data, not code) stored per *site key* (ATS platform + host, or employer domain):
   - `nav_steps`: the clicks the Navigator agent used to reach the form (by role+name/text, not brittle CSS),
   - `field_map`: field signature (label + type + options hash) → canonical meaning / answer key,
   - `buttons`: next/submit locators, `confirmation`: success markers,
   - stats: success/failure counts, last verified.
   A recipe is **created** after a successful generic-engine run, and **activated** only when the site is *recurring* (≥ 2 distinct jobs seen for that site key, or the host matches a known ATS platform). One-off sites keep nothing but the evidence bundle.
3. **Generic engine + Navigator agent** (LLM) as the fallback; its successful runs feed layer 2.
A recipe that fails twice is demoted (back to generic) and re-learned. The LLM never writes executable code into recipes; recipes are declarative data validated by a schema.

## Consequences
+ Cost per application falls over time; recurring sites become deterministic.
− Recipe quality must be monitored (success rate per recipe in analytics).
