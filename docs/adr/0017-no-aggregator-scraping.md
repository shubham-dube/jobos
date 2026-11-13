# ADR-0017: Aggregator jobs via alert emails, not scraping libraries

- Status: Accepted
- Date: 2026-11-13
- Related: ADR-0006, risk R1/R13, job-sources.md

## Context
The plan listed python-jobspy for LinkedIn/Indeed/Naukri discovery. On inspection it relies on `curl_cffi` browser
TLS-fingerprint impersonation to get past those sites' bot protection — i.e. detection evasion, which our
principles exclude and which raises account/IP-ban risk.

## Decision
- Do not use JobSpy or similar scrapers.
- Aggregator coverage comes from the founder's **own job-alert emails** (LinkedIn, Naukri, Indeed, Glassdoor,
  Wellfound…): the Inbox Clerk extracts each job, resolves it to the employer's ATS when the link allows (and adds
  that employer's board to the crawl list), otherwise stores it as an aggregator job (platform-native apply stays
  opt-in, ADR-0006).
- Employer coverage grows through **official public job-board APIs**: Greenhouse, Lever, Ashby, SmartRecruiters,
  Workable and Workday career sites (`cxs` JSON), with descriptions fetched lazily only for jobs passing cheap filters.

## Consequences
+ No ToS-evasion techniques; no proxy/fingerprint arms race.
− Aggregator coverage depends on the founder's alert subscriptions (set up broad alerts on each platform).
