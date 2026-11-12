# Glossary

Status: Draft

| Term | Meaning |
|---|---|
| **Master profile** | The user's single source of truth: identity, contact, work history, education, skills, links, documents, preferences, work authorization, demographic self-ID choices. Versioned. |
| **Answer bank** | Reusable answers to application questions ("Why do you want to work here?", "Notice period?", "Are you willing to relocate?"). Each answer has scope, provenance, and confidence. Grows every time the user answers an intervention. |
| **Search profile** | A saved set of job preferences (titles, locations, remote, salary floor, seniority, keywords, exclusions). A user may have several. |
| **Source** | A place jobs come from: ATS public API, job board, email job alert, company careers page. |
| **Posting** | A raw job listing as fetched from a source. |
| **Job (canonical)** | A deduplicated job that may have many postings (LinkedIn + Indeed + company ATS). Points to the **canonical apply URL**, preferably the company ATS. |
| **ATS** | Applicant Tracking System (Greenhouse, Lever, Ashby, Workday, iCIMS, SmartRecruiters, Taleo, SuccessFactors, Workable…). Most company application forms run on one. |
| **Adapter** | Deterministic code that knows how a specific ATS's application form works. |
| **Verification / legitimacy score** | Evidence-based score that the job is real, open, and not a scam. |
| **Match score** | How well a job fits the user's profile and preferences, with reasons and gaps. |
| **Application** | Our record of one attempt to apply to one job, with a state machine. |
| **Attempt** | One execution of the apply workflow for an application (there can be retries). |
| **Fill plan** | The resolved list of (field → value, source, confidence) before anything is typed. |
| **Intervention** | A request for the human: login, OTP, CAPTCHA, missing answer, review-before-submit. |
| **Submit gate** | The single policy checkpoint every application passes before the final submit click. |
| **Evidence bundle** | Screenshots, the final fill plan, uploaded files, confirmation page/email — proof of exactly what was submitted. |
| **Runner** | A process that controls a browser and executes browser tasks. Local runner = on the user's computer; cloud runner = in our infrastructure. |
| **Browser profile** | A persistent Chrome user-data directory holding cookies/logins for a user. |
| **Site account** | The user's account on a site (LinkedIn, Naukri, a company's Workday tenant). |
| **HITL** | Human-in-the-loop. |
| **Drift** | When a site changes its HTML so an adapter stops working. |
