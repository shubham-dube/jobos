# Vision, problem and principles

Status: In review

## 1. The problem

A serious job search today means:

1. **Discovery is fragmented.** Jobs are spread over LinkedIn, Indeed, Naukri, Glassdoor, Wellfound, company career pages, and thousands of ATS boards (Greenhouse, Lever, Ashby, Workday…). The same job appears 5 times with different titles; many listings are stale.
2. **A big share of postings are not real.** Greenhouse's own data counted ~19% of digital job-board postings in Q2 2026 as "ghost jobs" (applications received, no hiring activity). Monster's 2026 report: 95% of job seekers have seen at least one questionable listing. Outright scams steal identity documents and money.
3. **Applying is repetitive data entry.** Every ATS asks the same 30 fields in a different layout. Workday makes you create a new account *per employer*. Screening questions repeat ("notice period", "expected CTC", "sponsorship"). A careful application takes 15–45 minutes.
4. **Tracking is manual.** Confirmations, rejections, assessment links and interview invites land in email; people track them in spreadsheets or not at all, and forget what they wrote in each form.
5. **Existing automation makes it worse.** "Auto-apply" bots spray hundreds of generic applications from cloud servers, get LinkedIn accounts restricted, fill forms with hallucinated answers, and give the user no record of what was sent. Recruiters respond by filtering harder.

## 2. Vision

> **Your job search, run by a team of careful agents — and you only do the parts only you can do.**

JobOS is an autopilot that:
- **Finds** jobs everywhere they are posted, de-duplicates them, and traces each back to the company's own application page.
- **Verifies** that each job is real, open, and not a scam, and explains why.
- **Matches** jobs to the user's master profile and preferences with an honest fit score and the gaps.
- **Prepares** a grounded, tailored resume and answers — never inventing facts.
- **Applies** from a **real browser** with the user's own logged-in accounts, at a human pace.
- **Asks** the user (dashboard, phone, Telegram) only when it lacks information, needs a login/OTP/CAPTCHA, or policy requires review — and **remembers** the answer forever.
- **Tracks** the outcome automatically from the inbox and keeps a full evidence trail of what was submitted.

## 3. Who it is for

| Segment | Pain | Why they pay |
|---|---|---|
| **Founder (user #1)** | Needs a job search that runs itself | Dogfooding — we build what we use |
| Active job seekers (tech, 0–10 yrs) in India / US / remote | Volume of portals, repetitive forms | Time saved; more interviews |
| International students / visa-dependent candidates | Need sponsor-friendly jobs, deadlines | Filtering + speed |
| Laid-off professionals | Must search fast while stressed | Outplacement budgets often pay |
| Career coaches, placement cells, bootcamps | Manage many candidates | Multi-candidate "agency mode" (B2B) |

## 4. Product principles (in priority order)

1. **Volume *with* quality.** The system is built to apply to thousands of well-matched jobs, but only after match/eligibility/legitimacy checks, with human-like pacing per employer and review gates the user loosens over time (ADR-0015). A wrong application is worse than none.
2. **Never fabricate.** Every submitted value traces to a source the user owns. Unknown → ask.
3. **The user's real identity, the user's real browser.** Apply as the user would: their accounts, their device (or a dedicated, persistent profile), human pacing.
4. **Ask once, remember forever.** Every intervention makes the system more autonomous next time.
5. **Show your work.** Every application has an evidence bundle: what was filled, from where, screenshots, confirmation.
6. **Graceful degradation.** If a site breaks, the job falls back to a generic agent, then to a human, never to silent failure.
7. **Respect platforms where it matters.** Prefer applying on the employer's own ATS; treat platform-native automation (e.g. LinkedIn Easy Apply) as opt-in with stated risk.

## 5. North-star metric and supporting metrics

- **North star: interviews per week per active user.** (Not "applications sent" — that rewards spam.)
- Supporting:
  - Applications submitted per week (quality-gated)
  - **Autonomy rate**: % of applications submitted with zero interventions
  - **Human minutes per application** (target < 1 min in steady state)
  - Response rate (any human reply) per application, by source / resume variant
  - **Wrong-submission rate** (user-flagged incorrect field) — target ≈ 0
  - Account incidents (restrictions/bans) — target 0
  - Cost per submitted application (LLM + browser + proxy)

## 6. What success looks like

- **Phase 1 (founder):** In one month, the founder's search runs daily with < 15 minutes of human time per day, 100% of submissions verified correct, measurable interviews.
- **Phase 3 (beta):** 50–100 paying beta users, autonomy rate > 70%, no account bans, NPS > 40.
- **Long term:** the default way serious candidates run a job search; the same engine powers any "fill this form for me" workflow (see opportunity map).
