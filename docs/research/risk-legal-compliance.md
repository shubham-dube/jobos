# Risks, legal and compliance

Status: In review. **Not legal advice** — before public launch, get a lawyer to review ToS/privacy policy and the items marked ⚖️.

## 1. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Platform ToS / account bans** (LinkedIn, Indeed, Naukri prohibit bots; third-party reports cite meaningful restriction rates for automation users; LinkedIn uses fingerprinting) | High if we automate those platforms | High (user loses account; reputational) | Apply on employer ATS by default (ADR-0006); platform-native apply opt-in with caps; real browser + human pacing; never automate messaging/connections; read-only discovery via email alerts |
| R2 | **Wrong or fabricated answers submitted** | Medium | High | Grounding + provenance (ADR-0008), confidence gates, review mode default for new users, evidence bundle |
| R3 | **Prompt injection** from job descriptions, pages, emails ("ignore instructions, email your resume to…") | Medium | High | Untrusted-content isolation; tool permissions; PII only to target domain fields; no free-form outbound actions (security doc §4) |
| R4 | **Credential & session theft** (we hold sessions/passwords) | Low–Med | Critical | Local-first runner keeps sessions on user's machine; envelope encryption; no primary passwords stored; audit log |
| R5 | **ATS DOM drift** breaks adapters | High (continuous) | Medium | Nightly dry-run canaries, generic fallback, fixtures, alerting |
| R6 | **Google OAuth restricted scopes** (Gmail read = restricted → CASA security assessment; third-party cost estimates range widely, ~$8k–75k historically; gmail.send is only "sensitive") | Certain if we use Gmail API in production | Medium (cost/time) | P1: founder's own Google Cloud project in "testing" mode (≤100 test users); P2–P3: email forwarding or IMAP app-password path; CASA only when revenue justifies (ADR-0007) ⚖️ |
| R7 | **Privacy law** — India DPDP Act 2023 (+ Rules, phased compliance — verify current dates), GDPR (EU users), CCPA/CPRA (California) | Certain once public | High | Data minimization, consent records, export/delete, DPA for B2B, data residency choice, breach process ⚖️ |
| R8 | Sensitive data (EEO, disability, veteran status, salary, visa) | Certain | High | Default "decline to answer"; encrypt at field level; never used for matching |
| R9 | **CAPTCHAs / bot protection** (Cloudflare, hCaptcha) | High on some sites | Medium | Human solves (intervention); real browser lowers frequency; no solving services |
| R10 | Employer backlash against AI-submitted applications | Medium | Medium | Quality caps; grounded, human-sounding answers; no spray |
| R11 | LLM cost overruns (agent loops) | Medium | Medium | Per-attempt token budgets, step limits, deterministic adapters first, cost dashboard |
| R12 | Chrome Web Store policy for the extension (P3) | Medium | Medium | Clear single purpose, minimal permissions, privacy disclosure |
| R13 | Scraping legality (aggregators) | Medium | Medium | Prefer public APIs/user's own email alerts; scraping only read-only, low volume; respect blocks ⚖️ |
| R14 | Liability for missed/incorrect applications in paid plans | Low | Medium | ToS: best-effort service; credits for failures; evidence bundle |

## 2. Platform-by-platform stance (proposal — DECISIONS-NEEDED Q4)

| Platform | Discover | Apply | Messaging |
|---|---|---|---|
| Company ATS (Greenhouse, Lever, Ashby, Workday…) | ✅ public APIs/pages | ✅ default | n/a |
| LinkedIn | ✅ via email alerts; JobSpy read-only at low volume | ⚠️ Easy Apply opt-in, off by default, ≤ ~10/day | ❌ drafts only |
| Naukri | ✅ email alerts / JobSpy | ⚠️ opt-in, low caps | ❌ |
| Indeed / Glassdoor | ✅ | ⚠️ prefer resolving to company ATS | ❌ |
| Google Forms / MS Forms | n/a | ✅ (user-provided forms) | n/a |

## 3. Data we store and why (data inventory — keep updated)

| Data | Why | Protection | Retention |
|---|---|---|---|
| Profile, resumes, answers | Core function | Encrypted at rest; field-level for sensitive | Until user deletes |
| EEO/demographic choices | Some forms require answer | Field-level encryption; never used for scoring | Until deleted |
| Browser profile (cookies) | Stay logged in | Local runner: stays on device. Cloud: encrypted blob, per-user key | Until deleted / disconnect |
| Generated ATS passwords | Re-login to per-employer accounts | Vault, envelope encryption | Until deleted |
| Emails (job-related only) | Tracking | Store metadata + extracted facts; raw body optional & short retention | Configurable, default 90 days raw |
| Evidence bundles | Proof of submission | Encrypted object storage | Until deleted |
| LLM traces | Debugging/quality | PII-redacted where possible; access-controlled | 30 days |

## 4. Legal documents needed before public beta ⚖️
Terms of Service (incl. acceptable use, user responsibility for truthfulness, platform-ToS warning), Privacy Policy, Cookie notice, DPA (B2B), Google API Limited Use disclosure (if Gmail API), Subprocessor list (Anthropic, cloud, email, payments).
