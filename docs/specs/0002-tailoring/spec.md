# Spec 0002: Grounded resume tailoring and cover letters

Status: Accepted · Owner: founder + agents · Workstream: WS-J · Phase: P2 · PRD: FR-TAIL-1, FR-TAIL-2, FR-TAIL-3, NFR-1
Related ADRs: ADR-0008 (never fabricate), ADR-0015 (approval rules), ADR-0018 (Typst rendering)

## 1. Problem
One generic resume per role family undersells the candidate: recruiters and ATS keyword filters look for the
posting's language, and the founder's profile has far more material (6 roles, 12 projects, 72 skills) than fits
on one page. Choosing *which* true facts to show, in what order, and phrasing them in the job's vocabulary is
what a good human does by hand for every application. At thousands of applications that must be automatic —
and it must never invent anything (ADR-0008).

## 2. User stories
- As a candidate, every application I approve carries a one-page resume built for that job from my own facts.
- As a candidate, I can see exactly what changed versus my master profile (selected, dropped, reworded) and
  why each line is allowed (its source), before anything is submitted.
- As a candidate, when a form asks for a cover letter I get a short, specific, grounded letter — or none,
  if I say so.
- As a candidate, I can preview a tailored resume for any job from the dashboard and download the PDF.

## 3. Scope
**In:** select + reorder + light rephrase of profile items into a one-page variant; deterministic grounding
checker (+ optional LLM verifier); ATS-friendly PDF via Typst; storage as a per-job Document with provenance
and diff; automatic use in the application workflow (settings-gated); gate facts and approval-rule conditions;
dashboard preview/diff/download; grounded cover letters for cover-letter upload fields.
**Out:** multiple visual themes; DOCX output; LaTeX; editing the variant by hand in the UI (re-run or edit the
master profile instead); cover letters typed into free-text "Why us?" questions (already handled by the
resolver as `generated` answers).

## 4. Acceptance criteria (testable)
- [x] AC1 `tailor_resume(profile, job)` returns a variant whose every bullet cites ≥1 source id that exists in
      the profile and belongs to the bullet's item (or is a top-level fact); header/education/contact come from
      the profile deterministically, never from the LLM.
- [x] AC2 Grounding: a rephrased bullet is rejected if it contains a number, or a technology/proper-noun-like
      term, that is not in its sources, its item's skills/names, or the profile's skill list; rejected bullets
      fall back to the verbatim source text. Skills listed must be a subset of profile skills.
- [x] AC3 The PDF is A4/Letter (by job country), text-extractable, single column, standard headings, no
      images/tables/icons, and at most `max_pages` (default 1) pages — trimmed deterministically if longer.
- [x] AC4 The variant, diff (per bullet: source text vs final text, rephrased flag, rejected reason), dropped
      items and grounding report are stored with the Document; tailoring the same job twice reuses it unless
      forced.
- [x] AC5 With `tailoring.enabled`, the application workflow tailors before opening the form (durable step),
      uploads the tailored PDF as the resume, and falls back to the best uploaded resume on any failure
      (recorded as an event). Disabled → behaviour unchanged (FR-TAIL-3).
- [x] AC6 Gate facts include `tailored_resume` and `tailored_rephrased`; approval rules can require
      `max_tailored_rephrases`; the review screen shows the resume, its diff and download link.
- [x] AC7 Cover letters: when a page has a cover-letter upload (required, or optional and
      `cover_letter = always`), a grounded letter (every candidate claim cites profile ids; job context allowed
      only for terms present in the posting) is generated, rendered to PDF, stored per job and attached.
      `cover_letter = never` leaves optional fields empty and turns required ones into an intervention.
- [x] AC8 Dashboard: "Tailor resume" on a job, a document page with diff + download, settings toggles.
- [x] AC9 Tests: grounding unit tests (number/term injection rejected, honest rewording accepted), renderer
      test (text extraction, page limit), e2e apply with tailoring on (fake ATS receives the tailored PDF).

## 5. UX notes
Job page → **Tailor resume** → document page: PDF link, per-section list of lines with source text struck
through when reworded, badges *reworded* / *verbatim* / *kept original (reason)*, and a "dropped" list. The
review-before-submit screen links the same page. Settings → Tailoring JSON block (enabled, rephrase,
min_match_score, max_pages, cover_letter).

## 6. Data & API impact
- `documents`: + `job_id` (nullable FK → jobs), + `meta` JSONB (variant, diff, grounding, model, cost).
  Job-specific documents are never picked as defaults for other jobs.
- `POST /api/v1/jobs/{id}/tailor` (sync; `force` to regenerate) → document summary.
- `GET /api/v1/documents/{id}` (meta) and `GET /api/v1/documents/{id}/file` (owner download).
- CandidateSettings.tailoring; GateFacts.tailored_resume / tailored_rephrased;
  RuleConditions.max_tailored_rephrases.
- LLM tasks `tailor.resume`, `tailor.verify`, `tailor.cover_letter` (routable in the gateway).

## 7. Security & privacy considerations
- The job description is untrusted input: passed inside the `untrusted()` envelope; it can only influence
  *selection and wording*, never add facts (grounding is enforced in code, not by the prompt).
- Typst receives data through `sys.inputs` as JSON and renders it as plain strings — no markup or code
  injection from profile or posting text. No network access at render time (no Typst packages).
- PDFs are stored under the candidate's document path; downloads are owner-scoped like other documents.

## 8. Observability
Events `tailor.done` / `tailor.failed` on the application; ledger cost per tailoring; grounding counters
(rephrased, rejected) in the document meta and the review payload.

## 9. Risks
- Over-strict grounding rejects good rewording → falls back to verbatim text (safe; slightly less tailored).
- Under-strict grounding lets a synonym change meaning ("led" vs "helped") → optional LLM verifier and human
  review by default (auto-submit only via explicit rule).
- One-page trimming may drop something the user considers essential → item `priority` in the profile.

## 9b. Validation (2026-11-14, live, real profile)
- Databricks New Grad (London, A4): 1 page; 13 reworded / 2 reverted (one deterministic: a term not in the
  source; one by the verifier); grounded summary; cover letter 11/11 sentences kept. ≈ $0.09 per job
  (Sonnet tailor + Haiku verify + Sonnet letter).
- Figma Intern (US, Letter) via the real application workflow (dry run): tailored PDF generated in the workflow
  and attached on Greenhouse ("Shubham_Kumar_Dubey_Resume_Figma.pdf" visible on the form); gate facts
  `tailored_resume=true, tailored_rephrased=14`.
- Found and fixed while validating: verifier output budget; readable dates for summary grounding; singular/
  plural tech terms; verifier needs the item name; Greenhouse removes the file input after upload, so values
  filled in earlier passes are carried into the final plan/evidence; site notices that say "you can submit"
  no longer block the gate.

## 10. Open questions
- [ ] Q1 Should verified "reworded" lines be written back to the master profile as alternates? (later)
