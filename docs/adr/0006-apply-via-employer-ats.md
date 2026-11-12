# ADR-0006: Apply via employer ATS by default; platform-native apply is opt-in

- Status: Proposed — needs founder decision (DECISIONS-NEEDED Q4)
- Date: 2026-11-12
- Related: risk-legal-compliance.md R1, FR-APP-4, FR-DISC-3

## Context
LinkedIn, Naukri, Indeed prohibit automated use in their terms; third-party reports describe frequent restrictions for automation users. Applying on the employer's own ATS is where the application actually lands anyway and does not involve the aggregator account.

## Decision
- Default: resolve every job to the employer's ATS and apply there.
- Platform-native apply (LinkedIn Easy Apply, Naukri apply) is **off by default**; a candidate can enable it per platform after an explicit risk acknowledgement, with conservative caps (e.g. ≤10/day), active hours, and automatic pause on any warning signal (checkpoint pages, "unusual activity").
- Never automate messaging, connection requests, or profile edits on these platforms.

## Consequences
+ Much lower ban risk; higher-quality applications; cleaner product story.
− Some jobs exist only as Easy Apply → lower coverage unless opted in.
Revisit if data shows a large share of target jobs are Easy-Apply-only.
