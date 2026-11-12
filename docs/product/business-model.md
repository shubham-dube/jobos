# Business model, unit economics, go-to-market

Status: Draft — numbers are estimates to be replaced by measurements in Phase 1

## 1. Pricing hypothesis (to validate)

| Plan | For | Includes | Price (hypothesis) |
|---|---|---|---|
| Free | Try it / verifier users | Discovery + verification + tracking, 10 assisted applications/month, local runner only | ₹0 / $0 |
| Pro | Active seekers | 150 applications/month, tailoring, inbox tracking, Telegram, local runner | ₹999–1,499 / $25–35 per month |
| Pro + Cloud | Seekers who don't want to keep a laptop on | Pro + cloud runner (persistent browser, regional proxy) | ₹1,999–2,999 / $45–60 per month |
| Agency (B2B) | Coaches, placement cells, outplacement | Per-candidate seats, operator console, reporting | $15–40 per candidate/month, volume pricing |

Principles: transparent usage meter, easy cancel, no dark-pattern auto-renew (a known complaint against competitors), refunds for failed applications charged as credits.

## 2. Unit economics (rough model, verify in Phase 1)

Per submitted application, cloud mode:

| Cost | Assumption | Est. |
|---|---|---|
| LLM — matching/verification | mostly cached, small model where evals allow | $0.01–0.03 |
| LLM — form resolution + generated answers | ~20–40k input tokens, 2–4k output on `claude-opus-5-5` ($4/$20 per MTok), prompt caching on profile | $0.05–0.20 |
| LLM — generic-agent fallback (only when no adapter) | multi-step | $0.20–1.00 (minimize) |
| Browser minutes | ~5–10 min at cloud-browser rates | $0.01–0.02 |
| Residential/ISP proxy bandwidth | ~20–50 MB/application | $0.05–0.20 |
| **Total (adapter path)** | | **~$0.10–0.45** |

Local-runner mode removes browser and proxy costs → ~$0.06–0.25. **This is why local-first is also the cheaper model**, and why we invest in deterministic adapters (they make the LLM cost small and predictable).

Model routing to cheaper models (Sonnet 5.5 at $2/$10, Haiku 5.5 at $0.10/$0.50) is a founder decision and must be justified by evals (DECISIONS-NEEDED Q9).

Gross margin target at Pro: > 75%.

## 3. Go-to-market (draft)

1. **Founder-led, build in public:** the founder uses it; share results (interviews/week, time saved) on LinkedIn/X/Reddit.
2. **Free verifier as top of funnel:** "Is this job real?" extension/web tool (opportunity #2) — viral, harmless, creates accounts.
3. **Communities:** r/cscareerquestions, r/developersIndia, college groups, layoff communities.
4. **B2B pilots:** 2–3 college placement cells or bootcamps in India; 1–2 career coaches in US.
5. **Content:** honest guides on Workday, ghost jobs, ATS formatting.

## 4. Moats over time
- Answer bank + profile history per user (switching cost).
- Cross-user job intelligence (which postings are ghosts, which companies respond) — aggregated, anonymized.
- Library of ATS adapters + drift monitoring (operational moat).
- Trust brand: evidence bundles, never-fabricate guarantee.

## 5. Company/legal setup checklist (later)
Entity, terms of service, privacy policy, DPA template for B2B, payments (Stripe/Razorpay), trademark search for final name, domain.
