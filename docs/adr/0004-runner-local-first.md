# ADR-0004: Local-first runner; cloud runner later; shared runner protocol

- Status: Proposed — needs founder decision (DECISIONS-NEEDED Q3)
- Date: 2026-11-12
- Related: browser-execution.md, FR-HITL-4, FR-PLAT-2

## Context
The founder wants applications submitted from a real browser where their Google/email accounts are logged in, kept logged in, with manual login when necessary. Platforms detect bots using fingerprinting and IP reputation. Holding many users' session cookies in our cloud is a major security liability.

## Options
1. **Local runner first** (dedicated persistent Chrome profile on user's computer), cloud later.
2. Cloud-first (containerized/managed browsers + proxies).
3. Extension-only.

## Decision
Option 1. The runner connects outbound to the control plane using a versioned Runner Protocol; cloud runners (P3) and the extension (P3, assist mode) implement the same protocol.

## Consequences
+ Lowest ban risk, lowest cost, best privacy story ("your sessions never leave your computer"), fastest for the founder.
− User's computer must be on for applications to run; desktop packaging and updates; OS variance.
− Product users who want 24/7 need the paid cloud tier (P3).
Revisit if founder usage shows the "computer must be on" constraint is a serious blocker.
