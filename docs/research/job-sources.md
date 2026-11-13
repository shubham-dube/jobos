# Job sources — where jobs come from and how we get them

Status: Updated 2026-11-13 — implemented: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Workday (cxs), job-alert emails. Scraping libraries rejected (ADR-0017).

Original status: Draft. Endpoints below were confirmed via secondary sources; confirm against vendor docs when implementing each connector.

## 1. Source tiers

| Tier | Sources | Access | Quality | Risk |
|---|---|---|---|---|
| **A. ATS public boards** | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio… | Public unauthenticated JSON | Highest: it *is* the employer's posting; apply URL is canonical | Low (public APIs) |
| **B. Email job alerts** | LinkedIn, Naukri, Indeed, Glassdoor alerts the user already receives | User's own inbox (forward/IMAP/Gmail API) | Good, personalized | Low — user's own data |
| **C. Aggregators/boards (read)** | LinkedIn, Indeed, Glassdoor, Google Jobs, Naukri, ZipRecruiter (via JobSpy) | Scraping, rate-limited | Broad coverage, noisy, duplicates | Medium (ToS on scraping; IP blocks) |
| **D. Company career pages** | Custom sites, Workday tenants (`*.myworkdayjobs.com`), iCIMS, Taleo, SuccessFactors | Crawl / tenant JSON endpoints | High | Low–medium |
| **E. Community** | HN "Who is hiring", Wellfound, YC Work at a Startup, Reddit, Telegram/Discord channels | Mixed | Mixed; scams appear on Telegram | Varies; check ToS |
| **F. User-added** | Candidate pastes a URL or forwards an email | Direct | High | None |

## 2. ATS public endpoints (Tier A)
- **Greenhouse:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` (job detail incl. questions: `/jobs/{id}?questions=true`).
- **Lever:** `GET https://api.lever.co/v0/postings/{company}?mode=json` (EU host exists: `api.eu.lever.co`).
- **Ashby:** `GET https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`.
- **Workable, SmartRecruiters, Recruitee, Personio** — similar public endpoints; add in P2.
- Limits: no server-side search → we fetch whole boards and filter locally; confidential postings never appear.

### Company list (the hard part)
We need the *board tokens* (company slugs). Strategy:
1. Seed list from public sources (curated lists, past crawls, Common Crawl domain search for `boards.greenhouse.io/*`, `jobs.lever.co/*`, `jobs.ashbyhq.com/*`).
2. **Grow automatically:** every aggregator posting we resolve to an ATS URL adds that company's board token to the list.
3. Re-crawl boards on a schedule with ETag/If-Modified-Since where supported; store snapshots to compute posting age, reposts, closures (feeds ghost-job detection).

## 3. Direct-to-ATS resolution (FR-DISC-3)
Given a posting from LinkedIn/Indeed/Naukri:
1. If the posting's apply link points to an ATS → canonical = that URL.
2. Else search our ATS index for same company (normalized name/domain) + fuzzy title + location within ±14 days.
3. Else search the company careers page (known domain → crawl).
4. Record `resolution_confidence`. If none found, the job is "aggregator-only" (apply via aggregator only if the candidate opted in — ADR-0006).

## 4. Normalized posting schema (summary)
`source, source_job_id, url, apply_url, ats_type, company{name, domain}, title, normalized_title, seniority, employment_type, locations[], remote_type, salary{min,max,currency,period}, description_html, description_text, requirements[], posted_at, first_seen_at, last_seen_at, closed_at, raw` — full schema in `architecture/data-model.md`.

## 5. India-specific sources (if India is a target market — DECISIONS-NEEDED Q2)
- **Naukri** — largest; JobSpy covers search; Naukri sells its own auto-apply agent (Naukri Neo), so automation of applies via Naukri is a ToS/ban risk → opt-in only.
- **Instahyre, Cutshort, Hirist, Foundit, iimjobs, Wellfound India** — mostly require login; ToS review needed per site before any automation.
- Many Indian companies use Darwinbox, Keka, Zoho Recruit, Freshteam ATSs → candidate adapters for P2+.
- Google Forms are common for startup/college hiring → Google Forms adapter (P2).

## 6. Rate & politeness policy for all crawling
- Respect robots.txt for crawling (not required for documented public APIs, but stay polite).
- Per-host concurrency 1–2, exponential backoff on 429/5xx, cache aggressively.
- Identify our crawler with a generic UA for public APIs; never send user PII to sources.
