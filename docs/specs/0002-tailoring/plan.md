# Plan 0002: Grounded tailoring

## Components (apps/server/src/jobos/tailoring/)
| Module | Responsibility |
|---|---|
| `model.py` | `ResumeVariant` (header from profile; sections of items with bullets `{text, sources}`; skills; awards), `CoverLetter`, `GroundingReport`, `DiffLine`. |
| `sources.py` | Builds the citable source catalogue from the profile: highlight ids, `<item>:summary`, facts; per-item vocabulary. |
| `grounding.py` | Deterministic checker: ids exist and belong to the item, numbers ⊆ sources, entity-like terms ⊆ vocabulary, length bound, skills ⊆ profile. Returns accepted/rejected with reasons; rejected → verbatim fallback. Optional LLM verifier for reworded lines only. |
| `tailor.py` | LLM call (`tailor.resume`): picks items/bullets in order, optional rewording, skills ordering; then grounding, then assembly. Deterministic fallback (no LLM): priority + keyword overlap ordering, verbatim text. |
| `render.py` | Typst template (`templates/resume.typ`, `cover_letter.typ`) compiled with `typst` (`sys_inputs={"data": json}`); page counting via pypdf; trim loop until ≤ max_pages. |
| `cover_letter.py` | LLM call (`tailor.cover_letter`): 3–4 short paragraphs of sentences tagged `claim` (cites profile ids) or `context` (posting terms only); same checker; render PDF. |
| `service.py` | `tailor_for_job(s, gw, candidate_id, job_id, force)` / `cover_letter_for_job(...)`: idempotent per job, stores Document(job_id, meta). |

## Integration
1. Migration: `documents.job_id`, `documents.meta`.
2. `pick_resume` / `default_documents` ignore other jobs' documents.
3. Workflow: `tailor_step` after `start_step` when `settings.tailoring.enabled` and match ≥ min score;
   returns `{document_id, rephrased}` or `{error}`; ctx `resume_document_id` switches to it.
   Cover letter: in `_complete_page`, when the page has a cover-letter file field that needs a document →
   `cover_letter_step` → ctx.documents["cover_letter"].
4. Gate: facts + rule condition; review payload `resume` block.
5. API endpoints + dashboard pages (job button, document page, review link, settings already JSON).

## Testing
Unit (FakeProvider): grounding accept/reject matrix; tailor assembles + falls back; render page limit.
E2E: fake ATS apply with tailoring enabled → uploaded file is the tailored PDF (fake ATS echoes filename).
Live: real profile × Databricks/Harvey postings with OpenRouter; visual check of the PDF.
