# Product requirements (MVP → Beta)

Status: In review

Requirement IDs are stable; reference them in specs, tests and PRs. Phase tag: **P1** = founder MVP, **P2** = robust, **P3** = product beta, **P4+** = later.

## 1. Users and roles
- **Candidate** — the job seeker (founder is candidate #1).
- **Operator** (P4+) — coach/placement officer managing several candidates.
- **Admin** — us: support, abuse handling, feature flags.

## 2. Core user journeys
1. **Onboard:** sign in → upload resume(s) / LinkedIn export → system drafts master profile → candidate fixes gaps → sets search profile(s) and policies → connects email → installs/starts runner → logs into sites in the runner's browser.
2. **Daily loop (autonomous):** discovery runs on schedule → jobs verified, scored → shortlist → applications run within budget → interventions pushed to phone → candidate answers in seconds → applications continue → inbox updates statuses.
3. **Review:** candidate opens dashboard → sees pipeline, evidence of each submission, interviews scheduled, what needs attention.

## 3. Functional requirements

### 3.1 Master profile & documents
- **FR-PROF-1 (P1)** Import resume (PDF/DOCX) and extract a structured master profile (JSON Resume–compatible superset) with per-field confidence; candidate confirms.
- **FR-PROF-2 (P1)** Edit profile in the dashboard; profile is versioned; every application records the profile version used.
- **FR-PROF-3 (P1)** Store documents: resumes (multiple), cover letter templates, transcripts, certificates, ID-free by default (no government IDs in P1).
- **FR-PROF-4 (P1)** Preset answers for sensitive/standard questions: work authorization, sponsorship, notice period, expected/current compensation (per currency), relocation, EEO/diversity self-ID (default "decline to answer" unless the user sets otherwise).
- **FR-PROF-5 (P2)** Import LinkedIn data export (zip) to enrich profile.

### 3.2 Answer bank
- **FR-ANS-1 (P1)** Every answer the candidate gives to an intervention is saved with: canonical question, answer, scope (global / company / job), provenance, timestamp.
- **FR-ANS-2 (P1)** Semantic matching of new questions to existing answers with a confidence; above threshold → auto-use; below → ask.
- **FR-ANS-3 (P1)** Candidate can view/edit/delete answers; edits apply to future applications only.
- **FR-ANS-4 (P2)** Free-text answers (e.g. "Why this company?") generated per job, grounded only in profile + job + company facts, marked as generated, shown in review.

### 3.3 Search profiles & policies
- **FR-SRCH-1 (P1)** Multiple search profiles: titles/keywords, locations, remote/hybrid/onsite, seniority, salary floor, company include/exclude lists, industries, visa needs, recency.
- **FR-POL-1 (P1)** Policies per search profile: min match score, min legitimacy score, daily/weekly application cap, per-site caps, active hours, **submit mode** (`always_review` | `auto_if_confident` | `auto`), excluded companies (e.g. current employer).
- **FR-POL-2 (P1)** Never apply twice to the same canonical job, or to the same company+role within N days (configurable).

### 3.4 Discovery
- **FR-DISC-1 (P1)** Connectors: Greenhouse, Lever, Ashby public job-board APIs (company list seeded + grown automatically), JobSpy-based search for LinkedIn/Indeed/Glassdoor/Google/Naukri (read-only), email job-alert parsing.
- **FR-DISC-2 (P1)** Normalize postings into one schema (title, company, location(s), remote type, salary, seniority, description, posted_at, apply_url, ATS type).
- **FR-DISC-3 (P1)** Deduplicate into canonical jobs; resolve aggregator listings to the company ATS URL when it exists (FR-DISC-3 = "direct-to-ATS").
- **FR-DISC-4 (P2)** More connectors: Workable, SmartRecruiters, Recruitee, Workday tenant search, Wellfound, HN "Who is hiring", company career pages (crawler), Instahyre/Cutshort (subject to ToS review).
- **FR-DISC-5 (P1)** Scheduled runs per search profile (default: every 6h) + manual "run now"; candidate can paste any job URL to add it.

### 3.5 Verification
- **FR-VER-1 (P1)** Legitimacy score (0–100) with human-readable reasons: present on company ATS/careers page, apply domain matches company domain, posting age & repost history, company footprint, scam-pattern checks.
- **FR-VER-2 (P1)** Liveness check immediately before applying (page reachable, still accepting applications).
- **FR-VER-3 (P2)** Ghost-job signals over time (reposted every 30 days, open > 90 days, many identical postings).

### 3.6 Matching
- **FR-MATCH-1 (P1)** Hard filters from the search profile; then a fit score (0–100) with reasons, strengths, and gaps.
- **FR-MATCH-2 (P1)** Candidate feedback (👍/👎 + reason) on jobs is stored and used to tune scoring.

### 3.7 Tailoring
- **FR-TAIL-1 (P2)** Generate a job-specific resume variant from the master profile (reorder/select/rephrase only — no new facts); show diff; render ATS-friendly PDF.
- **FR-TAIL-2 (P2)** Cover letter when the form requires/allows one; grounded; reviewable.
- **FR-TAIL-3 (P1)** Until FR-TAIL-1 ships, choose the best of the candidate's uploaded resumes per job.

### 3.8 Applying
- **FR-APP-1 (P1)** Apply on Greenhouse, Lever, Ashby forms via deterministic adapters.
- **FR-APP-2 (P2)** Workday (incl. per-tenant account creation/sign-in), SmartRecruiters, iCIMS, Workable; Google Forms & Microsoft Forms.
- **FR-APP-3 (P2)** Generic fallback for unknown forms: LLM-guided navigation + the same extract/resolve/fill/verify pipeline.
- **FR-APP-4 (P2, opt-in)** Platform-native apply: Naukri, LinkedIn Easy Apply — off by default, explicit risk acknowledgement, strict caps.
- **FR-APP-5 (P1)** Every application passes the **submit gate** (policy + completeness + confidence + duplicate check).
- **FR-APP-6 (P1)** Evidence bundle: final fill plan with provenance, screenshots per page, uploaded files, confirmation page; immutable after submit.
- **FR-APP-7 (P1)** Human pacing: randomized delays, per-site concurrency = 1, daily caps, active hours.

### 3.9 Interventions (human-in-the-loop)
- **FR-HITL-1 (P1)** Types: `LOGIN_REQUIRED`, `MFA_CODE`, `CAPTCHA`, `MISSING_ANSWER`, `LOW_CONFIDENCE`, `REVIEW_BEFORE_SUBMIT`, `ACCOUNT_CREATION_CONSENT`, `UNKNOWN_PAGE`, `ATTESTATION`.
- **FR-HITL-2 (P1)** Intervention inbox in dashboard; batching (all missing questions of an application in one card).
- **FR-HITL-3 (P1)** Notifications: web push + Telegram bot (answer simple questions directly from Telegram). Email digest (P2). WhatsApp (P4).
- **FR-HITL-4 (P1)** Live browser takeover for login/CAPTCHA: on local runner the window is on the candidate's screen; on cloud runner a live view in the dashboard (P3).
- **FR-HITL-5 (P1)** Workflows wait durably (hours/days) and resume after answer; expire with a configurable timeout.

### 3.10 Accounts & sessions
- **FR-ACC-1 (P1)** Connections page shows each site and whether the runner's browser is logged in (health check), with "log in now" action.
- **FR-ACC-2 (P2)** Credential vault for generated per-employer ATS passwords (Workday etc.). Candidate's own primary passwords are never required — they log in manually once.
- **FR-ACC-3 (P2)** Email OTP/verification-link handling for in-flight attempts (scoped and time-limited).

### 3.11 Inbox tracking
- **FR-MAIL-1 (P2)** Connect email (see DECISIONS-NEEDED Q6). Classify job-related messages: confirmation, rejection, interview request, assessment, offer, recruiter outreach, job alert, verification/OTP.
- **FR-MAIL-2 (P2)** Link messages to applications; update status; surface deadlines.
- **FR-MAIL-3 (P1)** Parse job-alert emails as a discovery source (works with forwarding even before full inbox integration).

### 3.12 Dashboard
- **FR-DASH-1 (P1)** Pipeline (kanban/table by state), job feed (score, legitimacy, reasons), application detail (evidence), intervention inbox, profile & answer bank, search profiles & policies, connections/runner status.
- **FR-DASH-2 (P2)** Analytics: funnel, response rate by source/variant, time saved, costs.
- **FR-DASH-3 (P3)** Billing, plan usage, account settings, data export & delete.

### 3.13 Platform (product)
- **FR-PLAT-1 (P3)** Multi-tenant SaaS with auth (Google sign-in), org/candidate model ready for agency mode.
- **FR-PLAT-2 (P3)** Cloud runners with persistent profiles and sticky regional proxies.
- **FR-PLAT-3 (P3)** Billing (Stripe; Razorpay for India), plans & usage metering.
- **FR-PLAT-4 (P3)** Data export (JSON + files) and full account deletion.

## 4. Non-functional requirements
- **NFR-1 Correctness:** wrong-submission rate < 0.5% of fields (target 0); every submitted field has provenance.
- **NFR-2 Reliability:** no lost work — every workflow is durable; a runner crash resumes from the last completed page.
- **NFR-3 Security:** per-user encryption of sensitive data; secrets never logged; least-privilege tokens; audit log of every action.
- **NFR-4 Privacy:** data minimization; user can export/delete everything; compliance with India DPDP Act and GDPR basics.
- **NFR-5 Scalability:** architecture supports 10k active users with horizontal scale of workers/runners without redesign; P1 runs on one machine.
- **NFR-6 Cost:** target ≤ $0.30 all-in cost per submitted application at P3 (to be measured).
- **NFR-7 Observability:** every LLM call, browser step and workflow transition is traced and linked to the application.
- **NFR-8 Platform safety:** zero account bans in founder use; per-site rate policies.
- **NFR-9 Latency:** intervention notification delivered < 10 s after the workflow pauses.

## 5. Out of scope (until explicitly added)
Auto-messaging recruiters on LinkedIn; CAPTCHA-solving services; government ID handling; mobile app (web push/Telegram cover phones); non-English forms (P4+).
