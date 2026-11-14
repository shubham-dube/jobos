# ADR-0018: Render tailored resumes with our own Typst template (not RenderCV)

- Status: Accepted
- Date: 2026-11-14
- Deciders: founder, agents
- Related: Spec 0002, FR-TAIL-1, ADR-0008, ADR-0009; supersedes the "RenderCV" row in architecture/tech-stack.md

## Context
Tailored resumes must be ATS-friendly PDFs generated thousands of times, on the founder's Windows runner and in
the cloud, often without reliable network. Every line must map back to a profile fact (ADR-0008), so the
renderer is fed our own variant model. We evaluated RenderCV 2.8 (MIT): its templates import Typst packages
(e.g. fontawesome) that are downloaded from packages.typst.org **at render time** — this failed in our sandbox
and would be a runtime network dependency (and a supply-chain surface) for every render. It also has its own
YAML schema we would have to map to and keep in sync.

## Options
1. RenderCV — nice themes; runtime package downloads, schema coupling, icons we don't want for ATS.
2. HTML → PDF via the runner's Chromium — no new dependency; but rendering would need the runner (server-side
   tailoring could not render), and print CSS is fiddly for tight one-page layouts.
3. **Own Typst template + `typst` Python bindings (Apache-2.0)** — compiler bundled in the wheel, embedded
   fonts, offline, millisecond renders, data passed as JSON via `sys.inputs` (no markup injection).
4. LaTeX — heavy toolchain, slow, escaping hazards.

## Decision
Option 3. A single-column, icon-free Typst template in `jobos/tailoring/templates/`, data injected via
`sys.inputs`, no Typst package imports. RenderCV remains a reference for layout ideas only.

## Consequences
+ Offline, fast, deterministic; no runtime downloads; we control ATS-relevant structure.
− We own the template (small). Visual themes are out of scope for now.
Revisit if users ask for multiple designs — RenderCV themes could be vendored *with* their packages bundled.
