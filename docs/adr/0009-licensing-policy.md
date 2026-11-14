# ADR-0009: Dependency licensing policy

- Status: Accepted
- Date: 2026-11-12

## Context
We intend to sell a proprietary SaaS. Several relevant projects are AGPL-3.0 (e.g. Skyvern, ApplyPilot, Hyperbrowser's HyperAgent). AGPL obligations can extend to network use of modified code.

## Decision
- Allowed as dependencies: MIT, BSD, Apache-2.0, ISC, MPL-2.0 (file-level), PostgreSQL, Python-2.0.
- LGPL: allowed as unmodified dynamically-linked dependencies.
- GPL/AGPL: **not** included or linked in shipped code; dev-only tools (e.g. MinIO container locally) allowed. Using an AGPL service over the network unmodified requires an ADR.
- No copying code from AGPL/GPL repos; reading for ideas is fine.
- CI runs a license checker (`pip-licenses`, `license-checker`) against an allowlist.

## Consequences
+ Keeps commercial options open (including later open-core).
− Some useful projects become reference-only.
