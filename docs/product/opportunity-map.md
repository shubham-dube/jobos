# Opportunity map — what else we can solve

Status: In review — **founder to pick which go into which phase** (see DECISIONS-NEEDED Q1, Q2)

Rule from the founder: we build something only if **(a) it helps the founder directly** or **(b) people will pay for it**. Each idea is scored on both, plus uniqueness and effort.

Scores: 1 (low) – 5 (high). Effort: S / M / L / XL.

| # | Opportunity | Helps me | Pays | Unique | Effort | Recommendation |
|---|---|---|---|---|---|---|
| 1 | **Core autopilot**: discover → verify → match → apply → track | 5 | 5 | 3 | XL | **Core. Phase 1–3.** |
| 2 | **Ghost-job & scam verifier** (score + reasons, browser extension badge on any job page) | 4 | 3 | 5 | M | **Phase 2 inside product; Phase 4 as free standalone tool for acquisition.** |
| 3 | **Inbox tracker / auto-CRM**: classify confirmations, rejections, interviews, assessments; update pipeline; never miss a deadline | 5 | 4 | 3 | M | **Phase 2.** Very sticky. |
| 4 | **Universal answer bank + autofill extension**: fill *any* form (Google Forms, Microsoft Forms, Typeform, ATS) from the master profile, including ones the user opens manually | 5 | 4 | 3 | M | **Phase 3** (extension). Covers founder's Google Forms need. |
| 5 | **Direct-to-ATS resolver**: for any LinkedIn/Indeed/Naukri listing, find the same job on the employer's ATS | 4 | 3 | 5 | M | **Phase 1–2** (part of discovery). |
| 6 | **Workday/ATS account manager**: create per-employer accounts with generated passwords stored in a vault; handle email verification automatically | 5 | 4 | 4 | M | **Phase 2.** Workday is the #1 time sink. |
| 7 | **Referral / warm-intro copilot**: find alumni/ex-colleagues at the company, draft a short outreach note (user sends) | 4 | 4 | 4 | M | **Phase 4.** Referrals convert far better than cold applies. Draft-only (no LinkedIn automation). |
| 8 | **Interview prep pack**: per application, JD + company research + *exactly what you submitted* + likely questions | 4 | 4 | 3 | S | **Phase 3.** Cheap given the evidence bundle. |
| 9 | **Resume A/B analytics**: which resume variant/source gets replies | 3 | 3 | 4 | S | **Phase 3.** Needs volume + inbox tracking. |
| 10 | **Hiring signals / alerts**: company raised money, new team, hiring velocity, "first 24h" alerts | 3 | 3 | 3 | M | Phase 4. |
| 11 | **Agency mode (B2B)**: coaches, placement cells, bootcamps, outplacement firms manage many candidates, each with own profile/browser | 1 | 5 | 3 | L | **Phase 4–5.** Biggest revenue lever in India (colleges) and US (outplacement). Design multi-tenancy for it from day 1. |
| 12 | **Visa/sponsorship filter** (H-1B history, relocation-friendly employers) | 2 | 4 | 3 | S–M | Phase 4, if target market includes US/visa seekers. |
| 13 | **Salary intelligence & negotiation helper** | 3 | 3 | 2 | M | Later. |
| 14 | **Generalized form-agent platform**: the same engine for scholarships, university admissions, government/visa forms, vendor registrations, freelance proposals | 2 | 4 | 4 | L | **Long-term option.** Keep the form engine domain-agnostic so this is possible. |

## Things we deliberately do NOT do
- Mass blasting (hundreds/day) as a selling point.
- CAPTCHA-solving services, fake identities, fabricated experience.
- Automated LinkedIn messaging/connection requests (high ban risk; drafts only).
- Selling user data.

## Recommended sequencing (summary)
1. **For me first (Phase 1):** #1 core on easy ATSs + #5 resolver + answer bank + interventions.
2. **Make it robust (Phase 2):** #6 Workday accounts, #3 inbox tracker, #2 verifier, generic-agent fallback.
3. **Make it a product (Phase 3):** multi-tenant SaaS, cloud runners, billing, #4 extension, #8, #9.
4. **Grow (Phase 4+):** #2 free tool, #7 referrals, #11 agency mode, #10, #12.
